import ffmpeg
import os
import requests
import json
import numpy as np

from urllib.parse import urljoin
from dotenv import load_dotenv
from ftplib import FTP, error_perm


# Load .env file
load_dotenv()

# Create ftp dir if not exists function
def check_ftp_directory(ftp, path):
    try:
        ftp.cwd(path)
        ftp.cwd('/')
    except error_perm:
        ftp.mkd(path)
        ftp.cwd('/')


# Connection to archive server
with FTP(os.environ["ARCHIVE_HOST"], 
         os.environ["ARCHIVE_USER"], 
         os.environ["ARCHIVE_PASSWORD"]) as ftp:
    
    # API call to retrieve stations
    api_url = urljoin(os.environ['APP_URL'], '/api/v1/stations')
    rep = requests.get(api_url, auth=(os.environ['DEFAULT_USER'], os.environ['DEFAULT_PASSWORD']))
    
    stations = json.loads(rep.json()['data'])
    
    clips = []
    for key in stations.keys():
        st = stations[key]       
        st_dir = os.path.join(os.environ["ARCHIVE_COMPRESSED_PATH"], st['common_name'])
        
        check_ftp_directory(ftp, st_dir)
        
        source_path = os.path.join(os.environ["ARCHIVE_PATH"],
                                  st['common_name'], 
                                'woodcamrm-archived-clips')
        
        # Years folders
        years = [os.path.basename(pt) for pt in ftp.nlst(source_path)]
        
        for yr in years:
            year_dir = os.path.join(st_dir, yr)
            
            check_ftp_directory(ftp, year_dir)
            
            # Months folders
            source_year = os.path.join(source_path, yr)
            months = [os.path.basename(pt) for pt in ftp.nlst(source_year)]
        
            if len(months) == 0:
                print(f'{source_year} empty')
                ftp.rmd(source_year)
                
            else:
                for mth in months:
                    month_dir = os.path.join(year_dir, mth)
                    
                    check_ftp_directory(ftp, month_dir)
                    
                    # Days folders
                    source_month = os.path.join(source_year, mth)
                    days = [os.path.basename(pt) for pt in ftp.nlst(source_month)]
                    
                    if len(days) == 0:
                        print(f'{source_month} empty')
                        ftp.rmd(source_month)
                        
                    else:
                        for dy in days:
                            day_dir = os.path.join(month_dir, dy)
                            
                            check_ftp_directory(ftp, day_dir)
                            
                            source_day = os.path.join(source_month, dy)
                            
                            day_clips = ftp.nlst(source_day)
                            
                            if len(day_clips) == 0:
                                print(f'{source_day} empty')
                                ftp.rmd(source_day)
                                
                            else:
                                clips.append(day_clips)
    
    clips = list(np.concatenate(clips). flat)
    clips.sort()
                
        
    for ftp_clip in clips:
        print(f'Processing {ftp_clip}...')
        
        output_relpath = os.path.relpath(ftp_clip, os.environ['ARCHIVE_PATH']).replace('/woodcamrm-archived-clips', '')
        output_path = os.path.join(os.environ['ARCHIVE_COMPRESSED_PATH'], output_relpath)

        # Make local directories
        local_source_path = os.path.join('./sources', output_relpath)
        local_output_path = os.path.join('./outputs', output_relpath)
        
        os.makedirs(os.path.dirname(local_source_path), exist_ok=True)
        os.makedirs(os.path.dirname(local_output_path), exist_ok=True)
        
        # Download source file
        print('downloading...')
        with open(local_source_path, 'wb') as f:
            ftp.retrbinary('RETR ' + ftp_clip, f.write)
            
        # H264 encoding of the source video
        print('encoding...')
        stream = ffmpeg.input(local_source_path).output(local_output_path, vcodec='libx264', crf=23)
        
        try:
            ffmpeg.run(stream, quiet=True)
        except:
            print(f'!! Invalid data found in {ftp_clip} !!')
            continue
        
        # Upload encoded video
        print(f'uploading encoded video to {output_path}...')
        with open(local_output_path, 'rb') as f:
            ftp.storbinary('STOR ' + output_path, f)
            
        print('removing files...')
        # Remove distant source file
        #TODO: check if files are the same before deleting
        ftp.delete(ftp_clip)
        
        # Remove local files
        os.remove(local_source_path)
        os.remove(local_output_path)
        