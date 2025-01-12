import os
import base64
import time
import logging
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# log settings
LOG_DIR = "logs"
LOG_FILE = os.path.join(LOG_DIR, "gmail_checker.log")

# check log directory
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
  level=logging.INFO,
  format="%(asctime)s - %(level)s - %(message)s",
  handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)

# gmail api scope
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

def authenticate_gmail():
  """ Gmail API 인증 """
  creds = None
  credentials_path = "credentials.json"
  token_path = "token.json"
  if os.path.exists(token_path):
    creds = Credentials.from_authorized_user_file(token_path, SCOPES)
  if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
      creds.refresh(Request())
    else:
      flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
      creds = flow.run_local_server(port=0)
    with open(token_path, "w") as token:
        token.write(creds.to_json())
  return creds

def check_emails(service, sender_email, download_path):
    """ 특정 발신자의 이메일 확인 및 첨부파일 다운로드. """
    try:
      logging.info("메일 확인 중...")
      results = service.users().messages().list(userId="me", q=f"from:{sender_email}").execute()
      messages = results.get("messages", [])

      if not messages:
        logging.info("새로운 이메일이 없습니다.")
        return False

      for message in messages:
        msg = service.users().messages().get(userId="me", id=message["id"]).execute()
        payload = msg["payload"]
        headers = payload.get("headers", [])

        for header in headers:
          if header["name"] == "Subject":
            logging.info(f"제목: {headers['value']}")

        if "parts" in payload["body"]:
          for part in payload["body"]["parts"]:
            if part["filename"]:
              attachment_id = part["body"]["attachmentId"]
              attachment = service.users().messages().attachments().get(userId="me", messageId=message["id"], id=attachment_id).execute()
              data = base64.urlsafe_b64decode(
                  attachment["data"].encode("UTF-8")
              )
              file_path = os.path.join(download_path, part["filename"])
              with open(file_path, "wb") as f:
                f.write(data)
                logging.info(f"첨부파일 저장됨: {file_path}")

              return True
    except HttpError as error:
      logging.error(f"An error occurred: {error}")

    return False


def main():
  sender_email = "noreply@medium.com"
  download_path = "downloads"
  interval = 1

  if not os.path.exists(download_path):
    os.makedirs(download_path)

  creds = authenticate_gmail()
  service = build("gmail", "v1", credentials=creds)

  while True:
    if check_emails(service, sender_email, download_path):
      logging.info("첨부파일 다운로드 완료. 프로그램을 종료합니다.")
      break
    else:
      logging.info(f"첨부파일이 있는 메일을 찾지 못했습니다. {interval} 분 후 다시 시도합니다.")
      time.sleep(60 * interval)

if __name__ == "__main__":
  main()
