import numpy as np
# %load_ext autoreload
# %autoreload 2
import torch
from torch import nn
from torch.utils.data import DataLoader
from transformer import TransformerReg

class ASPCAP():
    """ 
    apogee dr16 aspcap instance
    """

    def __init__(self, npydata, device=torch.device('cpu')):
        self.dic = np.load(npydata, allow_pickle=True)
        self.device = device
    
                
    def __len__(self) -> int:
        num_sets = len(self.dic)
        return num_sets
    
    def __getitem__(self, idx: int):
        idx = self.dic[idx]['OBJ']
        flux = self.dic[idx]['flux']
        e_flux = self.dic[idx]['fluxerr']
        wave = self.dic[idx]['wave']
        
        prlx, e_prlx = self.dic[idx]['Gaia_parallax'], self.dic[idx]['Gaia_parallax_err']
        prlx_hogg, e_prlx_hogg = self.dic[idx]['spec_parallax'], self.dic[idx]['spec_parallax_err']

        flux = np.where(flux>0., flux, 0.)
        flux    = torch.tensor(flux.reshape(-1,1).astype(np.float32))
        prlx  = torch.tensor(prlx.reshape(-1,1).astype(np.float32))
        return flux.to(self.device), output.to(self.device)
    

if __name__ == "__main__":
    data_dir = "/scratch/jl14442/apogeedr14/"
    tr_file = "hogg19_spec_tr.npy"
    val_file = "hogg19_spec_val.npy"

    device = torch.device('cuda:0')
    TOTAL_SIZE = 6000
    BATCH_SIZE = 4

    ## Model parameters
    dim_val = 256 # This can be any value divisible by n_heads. 512 is used in the original transformer paper.
    n_heads = 8 # The number of attention heads (aka parallel attention layers). dim_val must be divisible by this number
    n_decoder_layers = 2 # Number of times the decoder layer is stacked in the decoder
    n_encoder_layers = 2 # Number of times the encoder layer is stacked in the encoder
    input_size = 1 # The number of input variables. 1 if univariate forecasting.
    enc_seq_len = 8575 # length of input given to encoder. Can have any integer value.
    dec_seq_len = 8 # length of input given to decoder. Can have any integer value.
    output_sequence_length = 1 # Length of the target sequence, i.e. how many time steps should your forecast
    max_seq_len = 8575 # What's the longest sequence the model will encounter? Used to make the positional encoder
    model = TransformerReg(dim_val=dim_val, input_size=input_size, 
                           batch_first=True, dec_seq_len=dec_seq_len, 
                           out_seq_len=output_sequence_length, n_decoder_layers=n_decoder_layers,
                           n_encoder_layers=n_encoder_layers, n_heads=n_heads,
                           max_seq_len=max_seq_len,
                           ).to(device)


    aspcap_tr  = ASPCAP(data_dir+tr_file, device=device)
    aspcap_val = ASPCAP(data_dir+val_file, device=device)
    # train_size = int(0.75*len(mastar))
    # val_size = len(mastar) - train_size
    # train_dataset, val_dataset = torch.utils.data.random_split(mastar, [train_size, val_size])
    print(len(aspcap_tr), len(aspcap_val))

    tr_loader  = DataLoader(aspcap_tr, batch_size=BATCH_SIZE, )
    val_loader = DataLoader(aspcap_val,  batch_size=BATCH_SIZE, )

    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

    total_loss = 0.
    num_epochs = 20
    # num_batches = train_size//BATCH_SIZE
    itr = 1
    num_iters  = 50
    
    
    for epoch in range(num_epochs):
        model.train()
        
        for batch, (x, y) in enumerate(tr_loader):
            start = time.time()

            output = model(x, y)
            loss = criterion(output, y)
            loss_value = loss.item()

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 0.5)
            optimizer.step()

            total_loss += loss.item()
            del x, y, output

            if itr%num_iters == 0:
                end = time.time()
                print(f"Epoch #%d  Iteration #%d  tr loss:%.4f time:%.2f s"%(epoch, itr, total_loss/itr, (end-start)*num_iters))
                    # writer.add_scalar('training loss = ',loss_value,epoch*itr)

                model.eval()
                total_val_loss = 0
                with torch.no_grad():
                    k=0
                    for x, y in val_loader:
                        output = model(x, y)
                        loss = criterion(output, y)
                        total_val_loss += loss.item()
                        k+=1
                        del x, y, output
                print("val loss:%.4f"%(total_val_loss/k))
            itr+=1

    torch.save(model.state_dict(), data_dir+"ap_prlx_trsfm_221018.pt")
    