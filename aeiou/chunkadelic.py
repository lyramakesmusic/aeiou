# AUTOGENERATED! DO NOT EDIT! File to edit: ../03_chunkadelic.ipynb.

# %% auto 0
__all__ = ['blow_chunks', 'process_one_file', 'main']

# %% ../03_chunkadelic.ipynb 6
import argparse 
import os 
from multiprocessing import Pool, cpu_count, Barrier
from functools import partial
from tqdm.contrib.concurrent import process_map  
import torch
import torchaudio
import math
from .core import is_silence, load_audio, makedir, get_audio_filenames, normalize_audio

# %% ../03_chunkadelic.ipynb 7
def blow_chunks(
    audio:torch.tensor,  # long audio file to be chunked
    new_filename:str,    # stem of new filename(s) to be output as chunks
    chunk_size:int,      # how big each audio chunk is, in samples
    sr=48000,            # audio sample rate in Hz
    norm=False,          # normalize audio, based on the max of the absolute value [global/channel]
    spacing=0.5,         # fraction of each chunk to advance between hops
    strip=False,    # strip silence: chunks with max power in dB below this value will not be saved to files
    thresh=-70      # threshold in dB for determining what counts as silence 
    ):
    "chunks up the audio and saves them with --{i} on the end of each chunk filename"
    chunk = torch.zeros(audio.shape[0], chunk_size)
    _, ext = os.path.splitext(new_filename)

        # normalize audio if requested
    if norm is True: # handle the most likely improper response defaulted to 'global'
        norm = 'global'
    if norm in ['global','channel']:
        print(f"normalizing {new_filename} with type {norm}")
        audio = normalize_audio(audio, norm)
    
    spacing = 0.5 if spacing is 0 else spacing # handle degenerate case as a request for the defaults
    
    start, i = 0, 0
    while start < audio.shape[-1]:
        out_filename = new_filename.replace(ext, f'--{i}'+ext) 
        end = min(start + chunk_size, audio.shape[-1])
        if end-start < chunk_size:  # needs zero padding on end
            chunk = torch.zeros(audio.shape[0], chunk_size)
        chunk[:,0:end-start] = audio[:,start:end]
        if (not strip) or (not is_silence(chunk, thresh=thresh)):
            torchaudio.save(out_filename, chunk, sr)
        else:
            print(f"skipping chunk {out_filename} because it's 'silent' (below threhold of {thresh} dB).",flush=True)
        start, i = start + int(spacing * chunk_size), i + 1
    return 

# %% ../03_chunkadelic.ipynb 8
def process_one_file(
    filenames:list,      # list of filenames from which we'll pick one
    args,                # output of argparse
    file_ind             # index from filenames list to read from
    ):
    "this chunks up one file"
    filename = filenames[file_ind]  # this is actually input_path+/+filename
    output_path, input_paths = args.output_path, args.input_paths
    new_filename = None
    
    for ipath in input_paths: # set up the output filename & any folders it needs
        if args.nomix and ('Mix' in ipath) and ('Audio Files' in path): return  # this is specific to the BDCT dataset, otherwise ignore
        if ipath in filename:
            last_ipath = ipath.split('/')[-1]           # get the last part of ipath
            clean_filename = filename.replace(ipath,'') # remove all of ipath from the front of filename
            new_filename = f"{output_path}/{last_ipath}/{clean_filename}".replace('//','/') 
            makedir(os.path.dirname(new_filename))      # we might need to make a directory for the output file
            break
    
    if new_filename is None:
        print(f"ERROR: Something went wrong with name of input file {filename}. Skipping.",flush=True) 
        return 
    try:
        audio = load_audio(filename, sr=args.sr)
        blow_chunks(audio, new_filename, args.chunk_size, sr=args.sr, norm=args.norm, spacing=args.spacing, strip=args.strip, thresh=args.thresh)
    except Exception as e: 
        print(f"Error loading {filename} or writing chunks. Skipping.", flush=True)

    return

# %% ../03_chunkadelic.ipynb 9
def main():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--chunk_size', type=int, default=2**17, help='Length of chunks')
    parser.add_argument('--sr', type=int, default=48000, help='Output sample rate')
    parser.add_argument('--norm', action='store_true', help='Normalize audio, based on the max of the absolute value [global/channel]')
    parser.add_argument('--spacing', type=float, default=0.5, help='Spacing factor, advance this fraction of a chunk per copy')
    parser.add_argument('--strip', action='store_true', help='Strips silence: chunks with max dB below <thresh> are not outputted')
    parser.add_argument('--thresh', type=int, default=-70, help='threshold in dB for determining what constitutes silence')
    parser.add_argument('--workers', type=int, default=min(32, os.cpu_count() + 4), help='Maximum number of workers to use (default: all)')
    parser.add_argument('--nomix', action='store_true',  help='(BDCT Dataset specific) exclude output of "*/Audio Files/*Mix*"')
    parser.add_argument('output_path', help='Path of output for chunkified data')
    parser.add_argument('input_paths', nargs='+', help='Path(s) of a file or a folder of files. (recursive)')
    args = parser.parse_args()

    print(f"  output_path = {args.output_path}")
    print(f"  chunk_size = {args.chunk_size}")

    print("Getting list of input filenames")
    filenames = get_audio_filenames(args.input_paths) 
    n = len(filenames)   
    print(f"  Got {n} input filenames") 

    print("Processing files (in parallel)")
    wrapper = partial(process_one_file, filenames, args)
    r = process_map(wrapper, range(0, n), chunksize=1, max_workers=args.workers)  # different chunksize used by tqdm. max_workers is to avoid annoying other ppl

    print("Finished")
