import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth

SCOPE = 'user-read-currently-playing user-read-playback-state user-modify-playback-state'


def build_auth_manager():
    return SpotifyOAuth(
        client_id=os.environ['SPOTIFY_CLIENT_ID'],
        client_secret=os.environ['SPOTIFY_CLIENT_SECRET'],
        redirect_uri=os.environ['SPOTIFY_REDIRECT_URI'],
        scope=SCOPE,
    )


def build_client(auth_manager):
    return spotipy.Spotify(auth_manager=auth_manager)
