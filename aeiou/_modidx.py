# Autogenerated by nbdev

d = { 'settings': { 'branch': 'main',
                'doc_baseurl': '/aeiou/',
                'doc_host': 'https://drscotthawley.github.io',
                'git_url': 'https://github.com/drscotthawley/aeiou/',
                'lib_path': 'aeiou'},
  'syms': { 'aeiou.chunkadelic': { 'aeiou.chunkadelic.blow_chunks': ('chunkadelic.html#blow_chunks', 'aeiou/chunkadelic.py'),
                                   'aeiou.chunkadelic.main': ('chunkadelic.html#main', 'aeiou/chunkadelic.py'),
                                   'aeiou.chunkadelic.process_one_file': ('chunkadelic.html#process_one_file', 'aeiou/chunkadelic.py')},
            'aeiou.core': { 'aeiou.core.fast_scandir': ('core.html#fast_scandir', 'aeiou/core.py'),
                            'aeiou.core.get_audio_filenames': ('core.html#get_audio_filenames', 'aeiou/core.py'),
                            'aeiou.core.is_silence': ('core.html#is_silence', 'aeiou/core.py'),
                            'aeiou.core.load_audio': ('core.html#load_audio', 'aeiou/core.py'),
                            'aeiou.core.makedir': ('core.html#makedir', 'aeiou/core.py')},
            'aeiou.datasets': { 'aeiou.datasets.AudioDataset': ('datasets.html#audiodataset', 'aeiou/datasets.py'),
                                'aeiou.datasets.AudioDataset.__getitem__': ('datasets.html#__getitem__', 'aeiou/datasets.py'),
                                'aeiou.datasets.AudioDataset.__init__': ('datasets.html#__init__', 'aeiou/datasets.py'),
                                'aeiou.datasets.AudioDataset.__len__': ('datasets.html#__len__', 'aeiou/datasets.py'),
                                'aeiou.datasets.AudioDataset.get_data_range': ('datasets.html#get_data_range', 'aeiou/datasets.py'),
                                'aeiou.datasets.AudioDataset.get_next_chunk': ('datasets.html#get_next_chunk', 'aeiou/datasets.py'),
                                'aeiou.datasets.AudioDataset.load_file_ind': ('datasets.html#load_file_ind', 'aeiou/datasets.py'),
                                'aeiou.datasets.AudioDataset.preload_files': ('datasets.html#preload_files', 'aeiou/datasets.py'),
                                'aeiou.datasets.FillTheNoise': ('datasets.html#fillthenoise', 'aeiou/datasets.py'),
                                'aeiou.datasets.FillTheNoise.__call__': ('datasets.html#__call__', 'aeiou/datasets.py'),
                                'aeiou.datasets.FillTheNoise.__init__': ('datasets.html#__init__', 'aeiou/datasets.py'),
                                'aeiou.datasets.Mono': ('datasets.html#mono', 'aeiou/datasets.py'),
                                'aeiou.datasets.Mono.__call__': ('datasets.html#__call__', 'aeiou/datasets.py'),
                                'aeiou.datasets.NormInputs': ('datasets.html#norminputs', 'aeiou/datasets.py'),
                                'aeiou.datasets.NormInputs.__call__': ('datasets.html#__call__', 'aeiou/datasets.py'),
                                'aeiou.datasets.NormInputs.__init__': ('datasets.html#__init__', 'aeiou/datasets.py'),
                                'aeiou.datasets.PadCrop': ('datasets.html#padcrop', 'aeiou/datasets.py'),
                                'aeiou.datasets.PadCrop.__call__': ('datasets.html#__call__', 'aeiou/datasets.py'),
                                'aeiou.datasets.PadCrop.__init__': ('datasets.html#__init__', 'aeiou/datasets.py'),
                                'aeiou.datasets.PadCrop.draw_chunk': ('datasets.html#draw_chunk', 'aeiou/datasets.py'),
                                'aeiou.datasets.PhaseFlipper': ('datasets.html#phaseflipper', 'aeiou/datasets.py'),
                                'aeiou.datasets.PhaseFlipper.__call__': ('datasets.html#__call__', 'aeiou/datasets.py'),
                                'aeiou.datasets.PhaseFlipper.__init__': ('datasets.html#__init__', 'aeiou/datasets.py'),
                                'aeiou.datasets.RandPool': ('datasets.html#randpool', 'aeiou/datasets.py'),
                                'aeiou.datasets.RandPool.__call__': ('datasets.html#__call__', 'aeiou/datasets.py'),
                                'aeiou.datasets.RandPool.__init__': ('datasets.html#__init__', 'aeiou/datasets.py'),
                                'aeiou.datasets.RandomGain': ('datasets.html#randomgain', 'aeiou/datasets.py'),
                                'aeiou.datasets.RandomGain.__call__': ('datasets.html#__call__', 'aeiou/datasets.py'),
                                'aeiou.datasets.RandomGain.__init__': ('datasets.html#__init__', 'aeiou/datasets.py'),
                                'aeiou.datasets.Stereo': ('datasets.html#stereo', 'aeiou/datasets.py'),
                                'aeiou.datasets.Stereo.__call__': ('datasets.html#__call__', 'aeiou/datasets.py')},
            'aeiou.hpc': { 'aeiou.hpc.HostPrinter': ('hpc.html#hostprinter', 'aeiou/hpc.py'),
                           'aeiou.hpc.HostPrinter.__call__': ('hpc.html#__call__', 'aeiou/hpc.py'),
                           'aeiou.hpc.HostPrinter.__init__': ('hpc.html#__init__', 'aeiou/hpc.py'),
                           'aeiou.hpc.freeze': ('hpc.html#freeze', 'aeiou/hpc.py'),
                           'aeiou.hpc.get_accel_config': ('hpc.html#get_accel_config', 'aeiou/hpc.py'),
                           'aeiou.hpc.load': ('hpc.html#load', 'aeiou/hpc.py'),
                           'aeiou.hpc.n_params': ('hpc.html#n_params', 'aeiou/hpc.py'),
                           'aeiou.hpc.save': ('hpc.html#save', 'aeiou/hpc.py')},
            'aeiou.spectrofu': { 'aeiou.spectrofu.main': ('spectrofu.html#main', 'aeiou/spectrofu.py'),
                                 'aeiou.spectrofu.process_one_file': ('spectrofu.html#process_one_file', 'aeiou/spectrofu.py'),
                                 'aeiou.spectrofu.save_stft': ('spectrofu.html#save_stft', 'aeiou/spectrofu.py')},
            'aeiou.viz': { 'aeiou.viz.audio_spectrogram_image': ('viz.html#audio_spectrogram_image', 'aeiou/viz.py'),
                           'aeiou.viz.embeddings_table': ('viz.html#embeddings_table', 'aeiou/viz.py'),
                           'aeiou.viz.pca_point_cloud': ('viz.html#pca_point_cloud', 'aeiou/viz.py'),
                           'aeiou.viz.plot_jukebox_embeddings': ('viz.html#plot_jukebox_embeddings', 'aeiou/viz.py'),
                           'aeiou.viz.print_stats': ('viz.html#print_stats', 'aeiou/viz.py'),
                           'aeiou.viz.proj_pca': ('viz.html#proj_pca', 'aeiou/viz.py'),
                           'aeiou.viz.show_pca_point_cloud': ('viz.html#show_pca_point_cloud', 'aeiou/viz.py'),
                           'aeiou.viz.spectrogram_image': ('viz.html#spectrogram_image', 'aeiou/viz.py'),
                           'aeiou.viz.tokens_spectrogram_image': ('viz.html#tokens_spectrogram_image', 'aeiou/viz.py')}}}