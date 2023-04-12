# AUTOGENERATED! DO NOT EDIT! File to edit: ../01_datasets.ipynb.

# %% ../01_datasets.ipynb 5
from __future__ import annotations  # for type hints, in LAION code samples
import numpy as np 
import torch
import torch.nn as nn
import torchaudio
from torchaudio import transforms as T
from torchvision import transforms as VT
import random
import os
import json
import tqdm
from multiprocessing import Pool, cpu_count
from urllib.parse import urlparse
from functools import partial
from .core import load_audio, get_audio_filenames, is_silence, untuple
from fastcore.utils import *
import webdataset as wds
import subprocess
import re
import pedalboard

# %% auto 0
__all__ = ['pp_calls', 'pipeline_return', 'RandomGain', 'PadCrop', 'PadCrop_Normalized_T', 'PhaseFlipper', 'FillTheNoise',
           'RandPool', 'NormInputs', 'Mono', 'Stereo', 'smoothstep', 'smoothstep_box', 'RandMask1D', 'AudioDataset',
           'fix_double_slashes', 'get_s3_contents', 'get_contiguous_range', 'get_all_s3_urls', 'IterableAudioDataset',
           'name_cache_file', 'wds_preprocess', 'log_and_continue', 'is_valid_sample', 'AudioWebDataLoader']

# %% ../01_datasets.ipynb 8
def pipeline_return(
    val,           # value to be returned (by calling function)
    x,             # original data-container that was passed in (tensor or dict)
    key='inputs',  # if x is dict, this key gets overwritten/added
    ):
    "little helper routine that appears at end of most augmentations, to compress code"
    if not isinstance(x, dict):
        return val
    else:
        x[key] = val
        return x

# %% ../01_datasets.ipynb 9
class RandomGain(nn.Module):
    "apply a random gain to audio"
    def __init__(self, 
        min_gain,    # minimum gain to apply
        max_gain,    # maximum gain to apply
        ):
        super().__init__()
        self.min_gain = min_gain
        self.max_gain = max_gain

    def __call__(self, x):
        signal = x if not isinstance(x, dict) else x['inputs']
        gain = random.uniform(self.min_gain, self.max_gain)
        signal = signal * gain
        return pipeline_return(signal, x)

# %% ../01_datasets.ipynb 14
class PadCrop(nn.Module):
    "Grabs a randomly-located section from an audio file, padding with zeros in case of any misalignment"
    def __init__(self, 
        n_samples,           # length of chunk to extract from longer signal
        randomize=True,      # draw cropped chunk from a random position in audio file
        redraw_silence=True, # a chunk containing silence will be replaced with a new one
        silence_thresh=-60,  # threshold in dB below which we declare to be silence
        max_redraws=2        # when redrawing silences, don't do it more than this many
        ):
        super().__init__()
        store_attr()     # sets self.___ vars automatically
    
    def draw_chunk(self, signal):
        "here's the part that actually draws a cropped/padded chunk of audio from signal"
        if len(signal.shape) < 2: signal = torch.unsqueeze(signal,0)
        n, s = signal.shape
        start = 0 if (not self.randomize) else torch.randint(0, max(0, s - self.n_samples) + 1, []).item()
        end = start + self.n_samples
        chunk = signal.new_zeros([n, self.n_samples])
        chunk[:, :min(s, self.n_samples)] = signal[:, start:end]
        crop_range = torch.tensor([start,end],dtype=int).to(signal.device) # making this a tensor helps preserve order in DataLoader 
        return chunk, crop_range
    
    def __call__(self, x):
        "when part of the pipline, this will grab a padded/cropped chunk from signal"
        signal = x if not isinstance(x, dict) else x['inputs']
        chunk, crop_range = self.draw_chunk(signal)
        num_redraws = 0
        while self.redraw_silence and is_silence(chunk, thresh=self.silence_thresh) and (num_redraws < self.max_redraws):
            chunk, crop_range = self.draw_chunk(signal)
            num_redraws = num_redraws+1
        if not isinstance(x, dict):  # multiple values, not handled by pipeline_return
            return chunk
        else:
            ##SHH: don't save original as x['uncropped'] unless all input files have the same length, otherwise torch.utils.data.DataLoader will complain about collating different lengths
            ##x['uncropped'] = x['inputs'] # save a copy (of the pointer) in case we want to quickly re-crop the same audio file
            x['inputs'], x['crop_range'] = chunk, crop_range  # crop_range reports where chunk was taken from
            return x 

# %% ../01_datasets.ipynb 16
class PadCrop_Normalized_T(nn.Module):
    """Variation on PadCrop.  source: Zach Evan's audio-diffusion repo"""
    def __init__(self, n_samples: int, randomize:bool = True):

        super().__init__()

        self.n_samples = n_samples
        self.randomize = randomize

    def __call__(self, source: torch.Tensor) -> Tuple[torch.Tensor, float, float]:

        n_channels, n_samples = source.shape

        upper_bound = max(0, n_samples - self.n_samples)

        offset = 0
        if(self.randomize and n_samples > self.n_samples):
            offset = random.randint(0, upper_bound + 1)

        t_start = offset / (upper_bound + self.n_samples)
        t_end = (offset + self.n_samples) / (upper_bound + self.n_samples)

        chunk = source.new_zeros([n_channels, self.n_samples])
        chunk[:, :min(n_samples, self.n_samples)] = source[:, offset:offset + self.n_samples]

        return (
            chunk,
            t_start,
            t_end
        )

# %% ../01_datasets.ipynb 21
class PhaseFlipper(nn.Module):
    "she was PHAAAAAAA-AAAASE FLIPPER, a random invert yeah"
    def __init__(self, 
        p=0.5  # probability that phase flip will be applied
        ):
        super().__init__()
        self.p = p
    def __call__(self, x):
        signal = x if not isinstance(x, dict) else x['inputs']
        out =  -signal if (random.random() < self.p) else signal
        return pipeline_return(out, x)

# %% ../01_datasets.ipynb 22
class FillTheNoise(nn.Module):
    "randomly adds a bit of noise, or not, just to spice things up"
    def __init__(self, 
        p=0.33       # probability that noise will be added
        ):
        super().__init__()
        self.p = p
    def __call__(self, x):
        signal = x if not isinstance(x, dict) else x['inputs']
        out = signal + 0.25*random.random()*(2*torch.rand_like(signal)-1) if (random.random() < self.p) else signal
        return pipeline_return(out, x)

# %% ../01_datasets.ipynb 23
class RandPool(nn.Module):
    "maybe (or maybe not) do an avgpool operation, with a random-sized kernel "
    def __init__(self, p=0.2):
        self.p, self.maxkern = p, 100
    def __call__(self, x):
        if (random.random() < self.p):
            signal = x if not isinstance(x, dict) else x['inputs']
            ksize = int(random.random()*self.maxkern)
            avger = nn.AvgPool1d(kernel_size=ksize, stride=1, padding=1)
            return pipeline_return( avger(signal), x )
        else:            
            return x   # do nothing

# %% ../01_datasets.ipynb 24
class NormInputs(nn.Module):
    "Normalize inputs to [-1,1]. Useful for quiet inputs"
    def __init__(self, 
        do_norm=True    # controllable parameter for turning normalization on/off
        ):
        super().__init__()
        self.do_norm = do_norm
        self.eps = 1e-2
    def __call__(self, x):
        signal = x if not isinstance(x, dict) else x['inputs']
        out =  signal if (not self.do_norm) else signal/(torch.amax(signal,-1)[0] + self.eps)
        return pipeline_return(out, x)

# %% ../01_datasets.ipynb 25
class Mono(nn.Module):
    "convert audio to mono"
    def __call__(self, x):
        signal = x if not isinstance(x, dict) else x['inputs']
        out = torch.mean(signal, dim=0) if len(signal.shape) > 1 else signal
        return pipeline_return(out, x)

# %% ../01_datasets.ipynb 26
class Stereo(nn.Module):
    "convert audio to stereo"
    def __call__(self, x):
        signal = x if not isinstance(x, dict) else x['inputs']
        # Check if it's mono
        if len(signal.shape) == 1: # s -> 2, s
            signal = signal.unsqueeze(0).repeat(2, 1)
        elif len(signal.shape) == 2:       
            if signal.shape[0] == 1: #1, s -> 2, s
                signal = signal.repeat(2, 1)    # copy mono to stereo
            elif signal.shape[0] > 2: #?, s -> 2,s
                signal = signal[:2, :]         # grab only first two channels
        return pipeline_return(signal, x)

# %% ../01_datasets.ipynb 28
def smoothstep(x, # a tensor of coordinates across a domain, e.g. [0,1]
    edge0=0.4, # "zero"/"left" side of smoothstep
    edge1=0.6, # "one"/"right" side of smoothstep
    ):
    "an s-shaped curve, 0's on left side and 1's at right side, with gradient zero at all 1's and 0's. cf. https://en.wikipedia.org/wiki/Smoothstep"
    x = torch.where(x < edge0, 0, x)
    x = torch.where(x > edge1, 1, x)
    x = torch.where( torch.logical_and(x >= edge0, x <= edge1) , (x - edge0) / (edge1 - edge0), x )
    return x * x * (3 - 2 * x)

# %% ../01_datasets.ipynb 29
def smoothstep_box(
    coords, # tensor of coordinate values
    edges = (0.2,0.3,0.5,0.6) # (left 1's boundary, left 0's boundary, right 0's boundary, right 1's boundary)
    ): 
    "makes a flat region of zeros that transitions smoothly to 1's via smoothsteps at the sides"
    assert edges[0] < edges[1] and edges[1] < edges[2] and edges[2] < edges[3], f"Edges should be in increasing order but you have edges = {edges}"
    right = smoothstep(coords, edge0=edges[2], edge1=edges[3])
    left = 1 - smoothstep(coords, edge0=edges[0], edge1=edges[1])
    return left + right

# %% ../01_datasets.ipynb 34
class RandMask1D(nn.Module):
    "Performs masking or 'cutout' along 1d data. Can support 'smooth sides' to the cutouts. Note that you probably want masking to be the *last* step in the augmentation pipeline"
    def __init__(self, 
        mask_frac=0.25,        # fraction of total input that is to be masked (helps compute no. of masked regions)
        mask_width=0.1,        # either a fraction of the total length (float < 1) or an exact integer value for length of each masked region
        mask_type='simple',    # 'simple'=hard sides to cuts, 'softstep'=smooth sides, 'nyquist'=nyquist-freq wave 0.5*(1,-1,1,-1,..)
        edge_width=0.2,        # for mask_type=smoothstep, fraction or integer value of transition regions to come in from the sides of zeros region
        per_channel=False,      # different masks on different channels; model can cheat if your inputs are mono
        verbose = False,       # show logging info
        ):
        super().__init__()
        if mask_width < 1: self.mask_width_frac = mask_width   # if float is given, set fraction of chunk length for each mask
        self.mask_frac,  self.mask_width, self.mask_type, self.edge_width, self.verbose = mask_frac, mask_width, mask_type, edge_width, verbose
        self.per_channel = per_channel
        self.mask = None       # mask is only setup (once and for all) when forward() is called

    def make_single_mask(self, x, mask_val=0):
        "allocate a 1D group of min_vals (zeros) amidst a bunch of 1's. Put the zeros/min_vals values in the middle"
        start = max(0, (x.shape[-1] - self.mask_width)//2 ) 
        end =   min(start + self.mask_width, x.shape[-1])   # don't go over the edge
        with torch.no_grad():
            self.mask = torch.ones(x.shape[-1]).to(x.device)
            if self.mask_type == 'simple': 
                self.mask[start:end] = mask_val                 
            elif self.mask_type == 'smoothstep':       
                coords = torch.linspace(0,1, steps=x.shape[-1]).to(x.device)
                ew = self.edge_width if isinstance(self.edge_width,int) else int((end-start)*self.edge_width) # edge width in samples
                self.mask = smoothstep_box(coords, edges=[coords[i] for i in [start, start+ew, end-ew, end]])
            elif self.mask_type == 'nyquist':
                self.mask[start:end:2], self.mask[start+1:end:2] = 0.5, -0.5  # nyquist noise, amplitude 0.5 seems good
            else:
                assert False, f"Error: Unsupported mask type: '{self.mask_type}'"

    def mask_once_1channel(self, 
        xc,            # one channel of x
        move=None,     # amount by which to shift the mask around, in samples
        start_loc = None, # can specify where to start from (typically leave this as None)
        ):
        "excises one mask region for one channel (hence '_1c') in one batch"
        # shift the mask forward or backward   
        shift_by = int((2*np.random.rand()-1)*xc.shape[-1]) if start_loc is None else start_loc
        with torch.no_grad():
            mask_view = torch.roll(self.mask, shift_by, -1).to(xc.device)   # move the mask around (as a view of original mask tensor)
        if self.mask_type != 'nyquist':
            return xc * mask_view # this does the excising
        else:
            return torch.where(mask_view == 1, xc, mask_view)
            

    def forward(self, x):
        signal = x if not isinstance(x, dict) else x['inputs']
        if self.mask is None:  # setup the mask if it hasn't been setup already
            if isinstance(self.mask_width, float):  # convert it from a fraction to an integer number of samples
                self.mask_width = int(signal.shape[-1] * self.mask_width_frac)
            self.make_single_mask(signal)
            self.n_masks =  int(self.mask_frac * signal.shape[-1]/self.mask_width)  # number of mask regions to add per channel. we will not worry about whether masks end up overlapping or not
            if self.verbose: print("\n MMMM-  RandMask1D: Mask engaged!  self.mask_width, self.n_masks = ",self.mask_width, self.n_masks,"\n")

        out = signal.clone().to(signal.device)  # make a copy so that we don't overwrite x
        while len(out.shape) < 3:     # add batch dim and channel dim for loop below if needed
            out = out.unsqueeze(0)
        assert len(out.shape) >= 3, f"Expected x to have 3 or more dimensions but x.shape = {x.shape}" # x.shape should be [b,c,n_samples]
        for bi in range(out.shape[0]):  # TODO: gotta be a way to do this all at once instead of 3 loops! 
            if self.per_channel:
                for c in range(out.shape[1]):  
                    for i in range(self.n_masks):
                        out[bi,c,:] = self.mask_once_1channel(out[bi,c,:]) 
            else:           # mask all channels at once. keeps model from cheating when mono has been doubled to L&R
                for i in range(self.n_masks):
                    out[bi,:,:] = self.mask_once_1channel(out[bi,:,:])  
        out = torch.reshape(out, signal.shape)
        if not isinstance(x, dict):      # too complex for pipeline_return
            return out
        else: 
            x['unmasked'] = x['inputs'] # save a copy (of the pointer) in case we want it later
            x['inputs'] = out
            return x 

# %% ../01_datasets.ipynb 44
class AudioDataset(torch.utils.data.Dataset):
    """
    Reads from a tree of directories and serves up cropped bits from any and all audio files
    found therein. For efficiency, best if you "chunk" these files via chunkadelic
    modified from https://github.com/drscotthawley/audio-diffusion/blob/main/dataset/dataset.py
    """
    def __init__(self, 
        paths,             # list of strings of directory (/tree) names to draw audio files from
        sample_rate=48000, # audio sample rate in Hz
        sample_size=65536, # how many audio samples in each "chunk"
        random_crop=True,  # take chunks from random positions within files
        load_frac=1.0,     # fraction of total dataset to load
        cache_training_data=False,  # True = pre-load whole dataset into memory (not fully supported)
        num_gpus=8,        # used only when `cache_training_data=True`, to avoid duplicates,
        redraw_silence=True, # a chunk containing silence will be replaced with a new one
        silence_thresh=-60,  # threshold in dB below which we declare to be silence
        max_redraws=2,        # when redrawing silences, don't do it more than this many
        augs='Stereo(), PhaseFlipper()', # list of augmentation transforms **after PadCrop**, as a string
        verbose=False,       # whether to print notices of reasampling or not
        return_dict=False    # False=return raw audio only, True=return dict of all kinds of info
        ):
        super().__init__()
    
        print("augs =",augs)
        # base_augs are always applied
        base_augs = 'PadCrop(sample_size, randomize=random_crop, redraw_silence=redraw_silence, silence_thresh=silence_thresh, max_redraws=max_redraws)'
        self.augs = eval(f'torch.nn.Sequential( {base_augs}, {augs} )')  if augs is not None else None 
        self.silence_thresh = silence_thresh
        self.redraw_silence = redraw_silence
        self.max_redraws = max_redraws
        self.sr = sample_rate
        self.cache_training_data = cache_training_data
        self.verbose = verbose
        self.return_dict = return_dict

        self.filenames = get_audio_filenames(paths)
        print(f"AudioDataset:{len(self.filenames)} files found.")
        self.n_files = int(len(self.filenames)*load_frac)
        self.filenames = self.filenames[0:self.n_files]
        if cache_training_data: self.preload_files()

        self.convert_tensor = VT.ToTensor()

    def load_file_ind(self, file_list,i): # used when caching training data
        return load_audio(file_list[i], sr=self.sr, verbose=self.verbose).cpu()

    def get_data_range(self): # for parallel runs, only grab part of the data -- OBVIATED BY CHUNKING.
        start, stop = 0, len(self.filenames)
        try:
            local_rank = int(os.environ["LOCAL_RANK"])
            world_size = int(os.environ["WORLD_SIZE"])
            interval = stop//world_size
            start, stop = local_rank*interval, (local_rank+1)*interval
            return start, stop
        except KeyError as e: # we're on GPU 0 and the others haven't been initialized yet
            start, stop = 0, len(self.filenames)//self.num_gpus
            return start, stop

    def preload_files(self):
        print(f"Caching {self.n_files} input audio files:")
        wrapper = partial(self.load_file_ind, self.filenames)
        start, stop = self.get_data_range()
        with Pool(processes=cpu_count()) as p:   # //8 to avoid FS bottleneck and/or too many processes (b/c * num_gpus)
            self.audio_files = list(tqdm.tqdm(p.imap(wrapper, range(start,stop)), total=stop-start))

    def __len__(self):
        return len(self.filenames)
    
    
    def get_next_chunk(self, 
        idx,     # the index of the file within the list of files
        ):
        "The heart of this whole dataset routine: Loads file, crops & runs other augmentations"
        audio_filename = self.filenames[idx]
        try:
            if self.cache_training_data:
                audio = self.audio_files[idx] # .copy()
            else:
                audio = load_audio(audio_filename, sr=self.sr, verbose=self.verbose)
            x = {'filename':audio_filename, 'inputs':audio} if self.return_dict else audio  # x is either audio or dict
            x = self.augs(x)      # RUN AUGMENTATION PIPELINE
            if isinstance(x, dict):
                x['inputs'] = x['inputs'].clamp(-1, 1)
            else:
                x = x.clamp(-1, 1)
            return x
        
        except Exception as e:
            print(f'AudioDataset.get_next_chunk: Error loading file {audio_filename}: {e}')
            return None
        
        
    def __getitem__(self, 
        idx     # the index of the file within the list of files
        ):
        "returns either audio tensor or a dict with lots of info"
        x = self.get_next_chunk(idx)  # x is either audio or a dict, depending on self.return_dict
        audio = x if not isinstance(x, dict) else x['inputs']
        
        # even with PadCrop set to reject silences, it could be that the whole file is silence; 
        num_redraws = 0 
        while (audio is None) or (self.redraw_silence and is_silence(audio, thresh=self.silence_thresh) \
            and (num_redraws < self.max_redraws)):
            next_idx = random.randint(0,len(self.filenames)-1)     # pick some other file at random
            x, num_redraws = self.get_next_chunk(next_idx), num_redraws+1
            audio = x if not isinstance(x, dict) else x['inputs']
    
        if self.verbose: print("__getitem__: x =",x)
        return self[random.randrange(len(self))] if (x is None) else x

# %% ../01_datasets.ipynb 57
def fix_double_slashes(s, debug=False):
    "aws is pretty unforgiving compared to 'normal' filesystems. so here's some 'cleanup'"
    cdsh_split = s.split('://')
    assert (len(cdsh_split) <= 2) and (len(cdsh_split) > 0), f'what kind of string are you using? s={s}'
    post = cdsh_split[-1]
    while '//' in post: 
        post = post.replace('//','/')
    if len(cdsh_split) > 1: 
        return cdsh_split[0] + '://' + post
    else:
        return post

# %% ../01_datasets.ipynb 62
def get_s3_contents(
    dataset_path,     # "name" of the dataset on s3
    s3_url_prefix='s3://s-laion-audio/webdataset_tar/',  # s3 bucket to check
    filter='',       # only grab certain filename / extensions
    recursive=True,  # check all subdirectories. RECOMMEND LEAVING THIS TRUE
    debug=False,     # print debugging info (don't rely on this info staying consistent)
    profile='default',      # name of the AWS profile credentials
    ):
    "Gets a list of names of files or subdirectories on an s3 path"
    if (dataset_path != '') and (not dataset_path.endswith('/')): 
        dataset_path = dataset_path + '/'
    dataset_path = fix_double_slashes(dataset_path)
    if not recursive:
        run_ls = subprocess.run(['aws','s3','ls',f'{s3_url_prefix}{dataset_path}','--profile',profile], capture_output=True)
    else:
        run_ls = subprocess.run(['aws','s3','ls',f'{s3_url_prefix}{dataset_path}','--recursive', '--profile',profile], capture_output=True)
        run_ls = subprocess.run(["awk",'{$1=$2=$3=""; print $0}'], input=run_ls.stdout, capture_output=True)
        run_ls = subprocess.run(["sed",'s/^[ \t]*//'], input=run_ls.stdout, capture_output=True)
    contents = run_ls.stdout.decode('utf-8')
    if debug: print("1 contents[:10] = \n",contents[:10]) # WARNING: this is a big long list
    contents = contents.split('\n') 
    contents = [x.strip() for x in contents if x]      # list of non-empty strings, without leading whitespace
    contents = [x.replace('PRE ','') if (x[-1]=='/') else x for x in contents]  # directories
    #if recursive:  # recursive flag weirdly adds redundant extra directory name taken from s3 url, so we should strip
        # in recursive cases we'll get the full directory path off the host name
        #main_dir = s3_url_prefix.split('/')[-2] # everything after the netloc
        #if debug: print("main_dir =",main_dir)
        #contents = [x.replace(f'{main_dir}/','').replace(dataset_path,'').replace('//','/') for x in contents]
        #contents = [x.replace(dataset_path,'').replace('//','/') for x in contents]

        #if debug: print("2 recursive contents[:10] = ",contents[:10])
    return [x for x in contents if filter in x] # return filtered list

# %% ../01_datasets.ipynb 71
def get_contiguous_range(
    tar_names, # list of tar file names, although the .tar part is actually optional
    ):
    "given a string of tar file names, return a string of their range if the numbers are contiguous. Otherwise return empty string"
    if len(tar_names) == 0:  return ''
    elif len(tar_names) == 1: return tar_names[-1]
    just_nums = [x.replace('.tar','') for x in tar_names]
    just_nums.sort(key=int) # sorts numerically but meaningfully preserves leading zeros in strings
    nums_arr = np.asarray(just_nums,  dtype=int)
    is_contiguous =  np.abs( (nums_arr - np.roll(nums_arr,1)) [1:] ).max() == 1
    if is_contiguous:   # {000000..000999}
        return '{' + f'{just_nums[0]}..{just_nums[-1]}' +'}'
    else:
        print("get_contiguous_range: File numbers not continuous")  # have to do more work
        return '' # empty string will signify no dice; signal for more work to be done

# %% ../01_datasets.ipynb 87
def get_all_s3_urls(
    names=[],    # list of all valid [LAION AudioDataset] dataset names, can include URLs in which case s3_url_prefix is ignored 
    subsets=[''],   # list of subsets you want from those datasets, e.g. ['train','valid']
    s3_url_prefix='s3://s-laion-audio/webdataset_tar/',   # prefix for those dataset names if no s3:// supplied in names
    recursive=True,  # recursively list all tar files in all subdirs
    filter_str='tar', # only grab files with this substring
    debug=False,     # print debugging info -- note: info displayed likely to change at dev's whims
    profile='',     # name of S3 profile to use (''=None)
    **kwargs
    ): 
    "get urls of shards (tar files) for multiple datasets in one s3 bucket"
    if s3_url_prefix is None:
        s3_url_prefix = ''
    #elif s3_url_prefix != '':
    #    if s3_url_prefix[-1] != '/':  s3_url_prefix = s3_url_prefix + '/'
    urls = []
    names = [''] if names == [] else names # for loop below
    subsets = [''] if subsets == [] else subsets # for loop below
    for name in names:
        purl = urlparse(name) # check if name already has a URL in it; if so, ignore s3_url_prefix
        if purl.scheme == '':
            s3_prefix = s3_url_prefix
        else:
            s3_prefix = f"{purl.scheme}://{purl.netloc}"
            name = name.replace(s3_prefix,'')
            if debug: 
                print("s3_prefix, name = ",s3_prefix, name)
        if debug: print(f"get_all_s3_urls: {s3_prefix}{name}:")
        for subset in subsets:
            contents_str = fix_double_slashes(f'{name}/{subset}/')
            if debug: print("contents_str =",contents_str, ", s3_prefix =",s3_prefix)
            tar_list = get_s3_contents(contents_str, s3_url_prefix=s3_prefix, recursive=recursive, filter=filter_str, debug=False, profile=profile)
            for tar in tar_list:
                tar = tar.replace(" ","\ ").replace("(","\(").replace(")","\)") # escape spaces and parentheses for shell
                s3_path  =  fix_double_slashes(f"{s3_prefix}/{tar} -")
                request_str = f"pipe:aws s3 --cli-connect-timeout 0 cp {s3_path}" 
                if profile != '': request_str += f" --profile {profile}"
                if debug: print("request_str = ",request_str)
                urls.append(fix_double_slashes(request_str))
    #urls = [x.replace('tar//','tar/') for x in urls] # one last double-check
    return urls

# %% ../01_datasets.ipynb 91
class IterableAudioDataset(torch.utils.data.IterableDataset):
    "Iterable version of AudioDataset, used with Chain (below)"
    def __init__(self, 
        paths,             # list of strings of directory (/tree) names to draw audio files from
        sample_rate=48000, # audio sample rate in Hz
        sample_size=65536, # how many audio samples in each "chunk"
        random_crop=True,  # take chunks from random positions within files
        load_frac=1.0,     # fraction of total dataset to load
        cache_training_data=False,  # True = pre-load whole dataset into memory (not fully supported)
        num_gpus=8,        # used only when `cache_training_data=True`, to avoid duplicates,
        redraw_silence=True, # a chunk containing silence will be replaced with a new one
        silence_thresh=-60,  # threshold in dB below which we declare to be silence
        max_redraws=2,        # when redrawing silences, don't do it more than this many
        augs='Stereo(), PhaseFlipper()', # list of augmentation transforms **after PadCrop**, as a string
        verbose=False,       # whether to print notices of reasampling or not
        ):
        super().__init__()
        self.this = AudioDataset(paths, sample_rate=sample_rate, sample_size=sample_size, random_crop=random_crop,
                                load_frac=load_frac, cache_training_data=cache_training_data, num_gpus=num_gpus,
                                redraw_silence=redraw_silence, silence_thresh=silence_thresh, max_redraws=max_redraws,
                                augs=augs, verbose=verbose)
        self.len = len(self.this)
        
    def __iter__(self):
        yield self.this.__getitem__(random.randint(0, self.len))

# %% ../01_datasets.ipynb 95
def name_cache_file(url):
    "provides the filename to which to cache a url"
    return re.findall(r's3:.* -',url)[0][:-2].replace('/','_').replace(' ','\ ').replace(':','_')

pp_calls = 0
def wds_preprocess(sample, sample_size=65536, sample_rate=48000, random_crop=True, verbose=False):
    "sampling and processing callback/handler for AudioWebDataLoader, below"
    global pp_calls
    pp_calls+= 1
    if verbose: print("pp_calls =",pp_calls)
    audio_keys = ("flac", "wav", "mp3", "aiff")
    found_key, rewrite_key = '', 'audio'  # SHH added 'audio' key for to match zach's webdataloader
    if verbose: print(f"----> Starting wds_preprocess: sample.items() = {sample.items()}")
    for k,v in sample.items():  # print the all entries in dict
        for akey in audio_keys:
            if k.endswith(akey): 
                found_key, rewrite_key = k, akey  # to rename long/weird key with its simpler counterpart
                break
        if '' != found_key: break 
    if '' == found_key:  # got no audio!   
        print("  wds_preprocess: Error: No audio in this sample:")
        for k,v in sample.items():  # print the all entries in dict
            print(f"    {k:20s} {repr(v)[:50]}")
        print("       wds_preprocess: Skipping it.")
        return None  # try returning None to tell WebDataset to skip this one ?   
    
    audio, in_sr = sample[found_key]
    if in_sr != sample_rate:
        if verbose: print(f"wds_preprocess: Resampling {filename} from {in_sr} Hz to {sample_rate} Hz",flush=True)
        resample_tf = T.Resample(in_sr, sample_rate)
        audio = resample_tf(audio)      
        
    # apply cropping and normalization
    #myop = torch.nn.Sequential(PadCrop(sample_size, randomize=random_crop), Stereo(), PhaseFlipper())
    #audio = myop(audio)
    
    # Pad/crop and get the relative timestamp
    #pad_crop = PadCrop(sample_size, randomize=random_crop)
    pad_crop = PadCrop_Normalized_T(sample_size, randomize=random_crop)
    audio, t_start, t_end = pad_crop(audio)

    # Make the audio stereo and augment by randomly inverting phase
    augs = torch.nn.Sequential(Stereo(), PhaseFlipper())
    audio = augs(audio)

    sample["timestamps"] = (t_start, t_end)
    sample["audio"] = audio  # regardless of what's above, let's also make a key pointing to the audio
    
    if found_key != rewrite_key:   # rename long/weird key with its simpler counterpart
        del sample[found_key]
    sample[rewrite_key] = audio 
    
    
    if verbose: print(f"     ---->  Leaving wds_preprocess: sample.items() = {sample.items()}")

    return sample

# %% ../01_datasets.ipynb 98
def log_and_continue(exn):
    """Call in an exception handler to ignore any exception, isssue a warning, and continue. 
    source: audio-diffusion repo"""
    print(f"Handling webdataset error ({repr(exn)}). Ignoring.")
    rank, world_size, worker, num_workers = wds.utils.pytorch_worker_info()
    print(f"Rank: {rank}, worker: {worker}")
    return True

def is_valid_sample(sample):
    """source: audio-diffusion repo"""
    silence = is_silence(sample["audio"])
    result = ("json" in sample) and ("audio" in sample) and not silence
    if result==False:
        print(f'is_valid_sample: result=False: ("json" in sample)={("json" in sample)}, ("audio" in sample) = {("audio" in sample)}, silence = {silence} ')
    return result

# %% ../01_datasets.ipynb 100
def AudioWebDataLoader(
    names=['FSD50K'],        # names of datasets. will search all available s3 urls
    subsets=[''],            # list of subsets you want from those datasets, e.g. ['train','valid']
    s3_url_prefix='s3://s-laion-audio/webdataset_tar/',   # prefix for those dataset names
    profile='',              # AWS S3 profile string to pass in (default: none)
    audio_file_ext="wav;flac;mp3;ogg;aiff;aif",  # extension(s) of audio files; passed to wds.to_tuple
    filter_str='tar',        # only grab files with this substring
    recursive=True,          # recursively list all tar files in all subdirs
    sample_size=65536,       # how long each sample to grab via PadCrop
    sample_rate=48000,       # standard sr in Hz
    random_crop=True,        # take chunks from random positions within files
    num_workers=os.cpu_count()//2,# number of PyTorch DataLoaders
    prefetch_factor=10,      # number of batches to pre-fetch
    batch_size=4,            # typical batch size
    shuffle_vals=[1000, 10000],  # values passed into shuffle as per WDS tutorials
    epoch_len=1000,          # how many passes/loads make for an epoch? wds part of this is not well documented IMHO
    debug=False,             # print info on internal workings
    verbose=False,           # unlike debug. this only prints in the callback
    callback=wds_preprocess, # function to call for additional user-based processing
    shuffle_urls=True,       # shuffle url list before it's passed to WebDataset
    shuffle_seed=None,       # seed for shuffling of urls
    zachs=True,               # use zach's data pipeline or hawley's
    **kwargs,                # what else to pass to callback
    ):
    "Sets up a WebDataLoader pipeline with some typical defaults for audio files"
    if verbose:
        print("AudioWebDataLoader: Note: 'Broken pipe' messages you might get aren't a big deal, but may indicate files that are too big.")
        print("AudioWebDataLoader: ", ', '.join(['{}={!r}'.format(k, v) for k, v in locals().items()]))
    if names is not list: names = list(names)
    urls = get_all_s3_urls(names=names, subsets=subsets, s3_url_prefix=s3_url_prefix, recursive=recursive, 
                           profile=profile, filter_str=filter_str, debug=debug) 
    if debug: print("AudioWebDataLoader: urls =\n",urls)
    os.environ["WDS_VERBOSE_CACHE"] = "1"  # tell webdataset to cache stuff
    if len(urls) > 0:
        if shuffle_urls:
            if shuffle_seed is not None: 
                random.seed(shuffle_seed)
            random.shuffle(urls)
            if debug: print("AudioWebDataLoader: shuffled urls =\n",urls)
        if zachs:
            dataset = wds.DataPipeline(
                wds.ResampledShards(urls), # Yields a single .tar URL
                wds.tarfile_to_samples(handler=log_and_continue), # Opens up a stream to the TAR file, yields files grouped by keys
                wds.shuffle(shuffle_vals[0], handler=log_and_continue), # SHH added
                wds.decode(wds.torch_audio, handler=log_and_continue),
                wds.map(partial(callback, sample_size=sample_size, sample_rate=sample_rate, verbose=verbose, random_crop=random_crop, **kwargs), handler=log_and_continue),
                wds.shuffle(shuffle_vals[1], handler=log_and_continue), # SHH added
                wds.select(is_valid_sample),
                wds.to_tuple("audio", "json", "timestamps", handler=log_and_continue),
                wds.batched(batch_size, partial=False)
            ).with_epoch(epoch_len//num_workers if num_workers > 0 else epoch_len)
        else:
            dataset = wds.DataPipeline(
                wds.ResampledShards(urls), #  cache_dir='./_mycache'), <-- not allowed
                wds.tarfile_to_samples(),
                wds.shuffle(shuffle_vals[0]),
                wds.decode(wds.torch_audio),
                wds.map(partial(callback, sample_size=sample_size, sample_rate=sample_rate, verbose=verbose, random_crop=random_crop, **kwargs)),
                wds.shuffle(shuffle_vals[1]),
                wds.to_tuple(audio_file_ext), # here's where it searches for the file extension
                wds.batched(batch_size),  
            ).with_epoch(epoch_len)
            
        return wds.WebLoader(dataset, num_workers=num_workers, prefetch_factor=prefetch_factor, **kwargs)
    else:
        print("*****ERROR: AudioWebDataLoader: No URLs found. Returning 'None'")
        return None
