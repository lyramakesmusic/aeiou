# AUTOGENERATED! DO NOT EDIT! File to edit: ../02_viz.ipynb.

# %% auto 0
__all__ = ['plotly_already_setup', 'embeddings_table', 'proj_pca', 'pca_point_cloud', 'on_colab', 'setup_plotly',
           'show_pca_point_cloud', 'print_stats', 'spectrogram_image', 'audio_spectrogram_image',
           'tokens_spectrogram_image', 'plot_jukebox_embeddings']

# %% ../02_viz.ipynb 5
import math
from pathlib import Path
from matplotlib.backends.backend_agg import FigureCanvasAgg
import matplotlib.cm as cm
import matplotlib.pyplot as plt 
from matplotlib.colors import Normalize
from matplotlib.figure import Figure
import numpy as np
from PIL import Image
import plotly.graph_objects as go


import torch
from torch import optim, nn
from torch.nn import functional as F
import torchaudio
import torchaudio.transforms as T
import librosa 
from einops import rearrange

import wandb
import numpy as np
import pandas as pd

from IPython.display import display, HTML  # just for displaying inside notebooks

# %% ../02_viz.ipynb 6
def embeddings_table(tokens):
    "make a table of embeddings for use with wandb"
    features, labels = [], []
    embeddings = rearrange(tokens, 'b d n -> b n d') # each demo sample is n vectors in d-dim space
    for i in range(embeddings.size()[0]):  # nested for's are slow but sure ;-) 
        for j in range(embeddings.size()[1]):
            features.append(embeddings[i,j].detach().cpu().numpy())
            labels.append([f'demo{i}'])    # labels does the grouping / color for each point
    features = np.array(features)
    #print("\nfeatures.shape = ",features.shape)
    labels = np.concatenate(labels, axis=0)
    cols = [f"dim_{i}" for i in range(features.shape[1])]
    df   = pd.DataFrame(features, columns=cols)
    df['LABEL'] = labels
    return wandb.Table(columns=df.columns.to_list(), data=df.values)

# %% ../02_viz.ipynb 7
def proj_pca(tokens, proj_dims=3):
    "this projects via PCA, grabbing the first _3_ dimensions"
    A = rearrange(tokens, 'b d n -> (b n) d') # put all the vectors into the same d-dim space
    if A.shape[-1] > proj_dims: 
        (U, S, V) = torch.pca_lowrank(A)
        proj_data = torch.matmul(A, V[:, :proj_dims])  # this is the actual PCA projection step
    else:
        proj_data = A
    return torch.reshape(proj_data, (tokens.size()[0], -1, proj_dims)) # put it in shape [batch, n, 3]

# %% ../02_viz.ipynb 9
def pca_point_cloud(
    tokens,                  # embeddings / latent vectors. shape = (b, d, n)
    color_scheme='batch',    # 'batch': group by sample, otherwise color sequentially
    output_type='wandbobj',  # plotly | points | wandbobj.  NOTE: WandB can do 'plotly' directly!
    mode='markers',    # plotly scatter mode.  'lines+markers' or 'markers'
    marker_size=3,
    ):
    "returns a 3D point cloud of the tokens using PCA"
    data = proj_pca(tokens).cpu().numpy()
    points = []
    if color_scheme=='batch':
        cmap, norm = cm.tab20, Normalize(vmin=0, vmax=data.shape[0])
    else: 
        cmap, norm = cm.viridis, Normalize(vmin=0, vmax=data.shape[1])
    for bi in range(data.shape[0]):  # batch index
        if color_scheme=='batch': [r, g, b, _] = [int(255*x) for x in cmap(norm(bi))] 
        for n in range(data.shape[1]):
            if color_scheme!='batch': [r, g, b, _] = [int(255*x) for x in cmap(norm(n))] 
            points.append([data[bi,n,0], data[bi,n,1], data[bi,n,2], r, g, b])

    point_cloud = np.array(points)
    
    #print("tokens.shape = ",tokens.shape, ", data.shape = ",data.shape,", len(points) = ",len(points))
    
    if output_type == 'points':
        return point_cloud
    elif output_type =='plotly':
        fig = go.Figure(data=[go.Scatter3d(
            x=point_cloud[:,0], y=point_cloud[:,1], z=point_cloud[:,2], 
            marker=dict(size=marker_size, opacity=0.6, color=point_cloud[:,3:6]),
            mode=mode, 
            # show batch index and time index in tooltips: 
            text=[ f'bi: {i}, ti: {j}' for i in range(data.shape[0]) for j in range(data.shape[1]) ]
            #text=[f'time index={ti:}' for ti in np.arange(n)]
            )])
        fig.update_layout(margin=dict(l=0, r=0, b=0, t=0)) # tight layout
        return fig
    else:
        return wandb.Object3D(point_cloud)

# %% ../02_viz.ipynb 11
# have to do a little extra stuff to make this come out in the docs.  This part taken from drscotthawley's `mrspuff` library
def on_colab():   # cf https://stackoverflow.com/questions/53581278/test-if-notebook-is-running-on-google-colab
    """Returns true if code is being executed on Colab, false otherwise"""
    try:
        return 'google.colab' in str(get_ipython())
    except NameError:    # no get_ipython, so definitely not on Colab
        return False 
    
plotly_already_setup = False
def setup_plotly(nbdev=True):
    """Plotly is already 'setup' on colab, but on regular Jupyter notebooks we need to do a couple things"""
    global plotly_already_setup 
    if plotly_already_setup: return 
    if nbdev and not on_colab():  # Nick Burrus' code for normal-Juptyer use with plotly & nbdev
        import plotly.io as pio
        pio.renderers.default = 'notebook_connected'
        js = '<script src="https://cdnjs.cloudflare.com/ajax/libs/require.js/2.3.6/require.min.js" integrity="sha512-c3Nl8+7g4LMSTdrm621y7kf9v3SDPnhxLNhcjFJbKECVnmZHTdo+IRO05sNLTH/D3vA6u1X32ehoLC7WFVdheg==" crossorigin="anonymous"></script>'
        display(HTML(js))
    plotly_already_setup = True 
    
def show_pca_point_cloud(tokens, color_scheme='batch', mode='markers'):
    "display a 3d scatter plot of tokens in notebook"
    setup_plotly()
    fig = pca_point_cloud(tokens, color_scheme=color_scheme, output_type='plotly', mode=mode)
    fig.show()

# %% ../02_viz.ipynb 15
def print_stats(waveform, sample_rate=None, src=None, print=print):
    "print stats about waveform. Taken verbatim from pytorch docs."
    if src:
        print(f"-" * 10)
        print(f"Source: {src}")
        print(f"-" * 10)
    if sample_rate:
        print(f"Sample Rate: {sample_rate}")
    print(f"Shape: {tuple(waveform.shape)}")
    print(f"Dtype: {waveform.dtype}")
    print(f" - Max:     {waveform.max().item():6.3f}")
    print(f" - Min:     {waveform.min().item():6.3f}")
    print(f" - Mean:    {waveform.mean().item():6.3f}")
    print(f" - Std Dev: {waveform.std().item():6.3f}")
    print('')
    print(f"{waveform}")
    print('')

# %% ../02_viz.ipynb 20
def spectrogram_image(spec, title=None, ylabel='freq_bin', aspect='auto', xmax=None, db_range=[35,120], justimage=False):
    "Modified from PyTorch tutorial https://pytorch.org/tutorials/beginner/audio_feature_extractions_tutorial.html"
    fig = Figure(figsize=(5, 4), dpi=100) if not justimage else Figure(figsize=(4.145, 4.145), dpi=100, tight_layout=True)
    canvas = FigureCanvasAgg(fig)
    axs = fig.add_subplot()
    im = axs.imshow(librosa.power_to_db(spec), origin='lower', aspect=aspect, vmin=db_range[0], vmax=db_range[1])
    if xmax:
        axs.set_xlim((0, xmax))
    if justimage:
        axs.axis('off')
        plt.tight_layout()
    else: 
        axs.set_ylabel(ylabel)
        axs.set_xlabel('frame')
        axs.set_title(title or 'Spectrogram (dB)')
        fig.colorbar(im, ax=axs)
    canvas.draw()
    rgba = np.asarray(canvas.buffer_rgba())
    im = Image.fromarray(rgba)
    if justimage: # remove tiny white border
        b = 15 # border size 
        im = im.crop((b,b, im.size[0]-b, im.size[1]-b))
        #print(f"im.size = {im.size}")
    return im

# %% ../02_viz.ipynb 21
def audio_spectrogram_image(waveform, power=2.0, sample_rate=48000, print=print, db_range=[35,120], justimage=False, log=False):
    "Wrapper for above, does Mel scale; Modified from PyTorch tutorial https://pytorch.org/tutorials/beginner/audio_feature_extractions_tutorial.html"
    n_fft = 1024
    win_length = None
    hop_length = n_fft//2 # 512
    n_mels = 128

    mel_spectrogram_op = T.MelSpectrogram(
        sample_rate=sample_rate, n_fft=n_fft, win_length=win_length, 
        hop_length=hop_length, center=True, pad_mode="reflect", power=power, 
        norm='slaney', onesided=True, n_mels=n_mels, mel_scale="htk")

    melspec = mel_spectrogram_op(waveform.float())
    if log:
        print_stats(melspec, print=print) 
        print(f"torch.max(melspec) = {torch.max(melspec)}")
        print(f"melspec.shape = {melspec.shape}")
    melspec = melspec[0] # TODO: only left channel for now
    return spectrogram_image(melspec, title="MelSpectrogram", ylabel='mel bins (log freq)', db_range=db_range, justimage=justimage)

# %% ../02_viz.ipynb 25
def tokens_spectrogram_image(tokens, aspect='auto', title='Embeddings', ylabel='index'):
    embeddings = rearrange(tokens, 'b d n -> (b n) d') 
    #print(f"tokens_spectrogram_image: embeddings.shape = ",embeddings.shape)
    fig = Figure(figsize=(10, 4), dpi=100)
    canvas = FigureCanvasAgg(fig)
    axs = fig.add_subplot()
    axs.set_title(title or 'Embeddings')
    axs.set_ylabel(ylabel)
    axs.set_xlabel('time frame')
    im = axs.imshow(embeddings.cpu().numpy().T, origin='lower', aspect=aspect, interpolation='none') #.T because numpy is x/y 'backwards'
    fig.colorbar(im, ax=axs)
    canvas.draw()
    rgba = np.asarray(canvas.buffer_rgba())
    return Image.fromarray(rgba)

# %% ../02_viz.ipynb 27
def plot_jukebox_embeddings(zs, aspect='auto'):
    "makes a plot of jukebox embeddings"
    fig, ax = plt.subplots(nrows=len(zs))
    for i, z in enumerate(zs):
        #z = torch.squeeze(z)
        z = z.cpu().numpy()
        x = np.arange(z.shape[-1])
        im = ax[i].imshow(z, origin='lower', aspect=aspect, interpolation='none')

    #plt.legend()
    plt.ylabel("emb (top=fine, bottom=coarse)")
    return {"chart": plt}
