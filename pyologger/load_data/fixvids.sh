# will require having ffmpeg installed (brew install ffmpeg, may also need to install command line tools)
ffmpeg -i camera-96-20240617-162855-00003.mov -c:v copy -c:a aac -map 0 -movflags +faststart fixed_video_output.mp4