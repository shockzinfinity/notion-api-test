import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# OAuth 2.0 인증 범위
SCOPES = ['https://www.googleapis.com/auth/youtube.readonly']

def authenticate_youtube():
  """OAuth 2.0을 통해 YouTube API 인증."""
  creds = None
  # 기존 인증 토큰 파일 확인
  if os.path.exists('token.json'):
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)
  if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
      creds.refresh(Request())
    else:
      flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
      creds = flow.run_local_server(port=0)
    # 인증 토큰 저장
    with open('token.json', 'w') as token:
      token.write(creds.to_json())
  return creds

def get_all_playlists(youtube):
  """내가 저장한 모든 재생목록을 가져오는 함수."""
  playlists = []
  
  # 1. 내가 만든 재생목록 가져오기
  try:
    request = youtube.playlists().list(
        part="snippet",
        mine=True,
        maxResults=50
    )
    while request:
      response = request.execute()
      for item in response.get("items", []):
        playlists.append({
            "title": item["snippet"]["title"],
            "id": item["id"],
            "type": "created"  # 내가 만든 재생목록
        })
      request = youtube.playlists().list_next(request, response)
  except Exception as e:
    print(f"내가 만든 재생목록을 가져오는 중 오류 발생: {e}")

    # 2. 내가 저장한 재생목록 가져오기 (저장된 재생목록)
  try:
    request = youtube.playlists().list(
        part="snippet",
        maxResults=50,
        mine=False  # 내가 만든 재생목록이 아닌 저장된 재생목록
    )
    while request:
      response = request.execute()
      for item in response.get("items", []):
        playlists.append({
            "title": item["snippet"]["title"],
            "id": item["id"],
            "type": "saved"  # 내가 저장한 재생목록
        })
      request = youtube.playlists().list_next(request, response)
  except Exception as e:
    print(f"내가 저장한 재생목록을 가져오는 중 오류 발생: {e}")

  return playlists

def main():
  creds = authenticate_youtube()
  youtube = build('youtube', 'v3', credentials=creds)

  print("내가 저장한 모든 재생목록 가져오는 중...")
  playlists = get_all_playlists(youtube)

  if playlists:
    print(f"총 {len(playlists)}개의 재생목록을 찾았습니다:")
    for playlist in playlists:
      print(f"- {playlist['title']} (ID: {playlist['id']}, Type: {playlist['type']})")
  else:
    print("재생목록을 찾지 못했습니다.")

if __name__ == "__main__":
  main()
