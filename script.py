import asyncio
import json
import urllib.request
import urllib.parse
from pathlib import Path

import shazamio
import yt_dlp
import soundfile as sf
import librosa
from googleapiclient.discovery import build


SEARCH_VID_API_KEY = "key" # API key: KEEP IT SEECRET!
AUDIO_SPLIT_DURATION = 30


class YouTubeShazamException(Exception):
    ...


class ZeroDurationError(YouTubeShazamException):
    def __init__(self, file_name):
        self.file = file_name

    def __str__(self):
        return f"{self.file} has no duration."


class VideoNotFoundError(YouTubeShazamException):
    def __init__(self, title):
        self.title = title

    def __str__(self):
        return f"{self.title}'s id was not founded on YouTube"


class FileAlreadyExists(YouTubeShazamException):
    def __init__(self, file_name):
        self.file_name = file_name

    def __str__(self):
        return f"{self.file_name} is already exists."


def exists_file_check(file: Path):
    if file.exists():
        raise FileAlreadyExists(file.name)


def SearchVid(title):
    title = title.lower().replace(" ", "+")
    youtube = build('youtube', 'v3', developerKey=SEARCH_VID_API_KEY)

    request = youtube.search().list(
        part="snippet",
        type="video",
        q=title,
        maxResults=1
    )
    response = request.execute()

    try:
        try:
            exists_file_check(Path(f"./music/{response["items"][0]["snippet"]["title"]}.mp3"))
        except YouTubeShazamException as e:
            print(e)
            raise e
        return response["items"][0]["id"]["videoId"]
    except KeyError as e:
        raise VideoNotFoundError(title)


def download_audio(video_url, output_path):
    file_name = ""

    def my_hook(d):
        nonlocal file_name
        if d['status'] == 'finished':
            print("Done downloading, now converting ...")
            file_name = d['filename']

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f'{output_path}/%(title)s.%(ext)s',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'writesubtitles': False,
        'allsubtitles': False,
        'quiet': True,
        'timeout': 300,
        'retries': 10,
        'http2': True,
        'progress_hooks': [my_hook],
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([video_url])
    return file_name


def get_music_duration(file):
    y, sr = librosa.load(file)
    return librosa.get_duration(y=y, sr=sr)


async def main():
    offset = 0.0
    shazam = shazamio.Shazam()
    previousmusic = ""
    file = Path(input("Введите путь к аудиофайлу: "))
    while True:
        y, sr = librosa.load(file, offset=offset, duration=offset + AUDIO_SPLIT_DURATION)
        if librosa.get_duration(y=y, sr=sr) > 0.0:
            break
        sf.write(str(file.parent).replace("\\", "/") + "/trimmed.wav", y, sr)
        out = await shazam.recognize(
            str(file.parent).replace("\\", "/") + "/trimmed.wav")
        if f"{out["track"]["subtitle"]}-{out["track"]["title"]}".lower() == previousmusic:
            offset += AUDIO_SPLIT_DURATION
            continue
        try:
            video_id = SearchVid(f"{out["track"]["subtitle"]}-{out["track"]["title"]}")
            video_url = f"https://youtube.com/watch?v={video_id}"
            file_name = download_audio(video_url, "music")
            offset += get_music_duration(
                ".".join(file_name.split(".")[:-1]) + ".mp3")
        except YouTubeShazamException as e:
            offset += AUDIO_SPLIT_DURATION
            print(e)
        previousmusic = f"{out["track"]["subtitle"]}-{out["track"]["title"]}".lower()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
