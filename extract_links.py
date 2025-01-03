import os
import glob
from lxml import etree
import multiprocessing
from itertools import islice
import json

# 리스트를 hashmap 으로 변환
def list_to_map(data_list):
  return {item['url']: item for item in data_list}

# ✅ 글로벌 비교 함수
def global_diff_update(old_list, new_list):
  """
  old_list와 new_list를 글로벌 HashMap을 사용하여 비교합니다.
  """
  old_map = list_to_map(old_list)
  new_map = list_to_map(new_list)

  # ✅ 추가된 항목 (new_map에만 존재)
  added = [item for url, item in new_map.items() if url not in old_map]
  
  # ✅ 삭제된 항목 (old_map에만 존재)
  removed = [url for url in old_map if url not in new_map]
  
  # ✅ 변경되지 않은 항목 (두 맵에 모두 존재)
  unchanged = [item for url, item in new_map.items() if url in old_map]
  
  # ✅ 최종 리스트: 유지된 항목 + 추가된 항목
  final_list = unchanged + added
  
  return final_list, removed
  
def compare_batches(old_map, new_batch):
  """
  각 배치를 old_map과 비교하여 added, removed, unchanged를 반환합니다.
  """
  new_map = {item['url']: item for item in new_batch}
  added = [item for url, item in new_map.items() if url not in old_map]
  removed = [url for url in old_map if url not in new_map]
  unchanged = [item for url, item in new_map.items() if url in old_map]
  return {'added': added, 'removed': removed, 'unchanged': unchanged}

# ✅ 멀티프로세싱을 활용한 글로벌 비교
def multiprocessing_global_diff(old_list, new_list, num_processes=4):
  """
  글로벌 HashMap을 기반으로 멀티프로세싱을 통해 old_list와 new_list를 비교합니다.
  """
  old_map = list_to_map(old_list)
  batch_size = len(new_list) // num_processes + 1
  new_batches = [new_list[i:i + batch_size] for i in range(0, len(new_list), batch_size)]

  with multiprocessing.Pool(num_processes) as pool:
    results = pool.starmap(compare_batches, [(old_map, batch) for batch in new_batches])
  
  # 결과 병합
  final_added = []
  final_removed = []
  final_unchanged = []
  
  for result in results:
    final_added.extend(result['added'])
    final_removed.extend(result['removed'])
    final_unchanged.extend(result['unchanged'])
  
  final_list = final_unchanged + final_added
  
  return final_list, final_removed

# ✅ HTML 파일에서 URL과 제목을 추출하는 함수 (XPath 사용)
def extract_links_from_html(file_path):
  """
  XPath를 사용하여 HTML 파일에서 <body> → <section> → <ul> → <li> → <a> 구조로 URL과 제목을 추출합니다.
  """
  links = []  # 결과를 저장할 리스트
    
  # HTML 파일 읽기
  with open(file_path, 'r', encoding='utf-8') as file:
    content = file.read()
    parser = etree.HTMLParser()
    tree = etree.fromstring(content, parser)  # lxml을 사용해 HTML 파싱

    # XPath를 사용해 a 태그 찾기
    li_tags = tree.xpath('//body/section/ul/li')
    
    for li in li_tags:
      a_tag = li.xpath('./a[@class="h-cite"]')
      time_tag = li.xpath('./time[@class="dt-published"]')

      url = a_tag[0].get('href') if a_tag else None  # href 속성 추출
      title = a_tag[0].text.strip() if a_tag and a_tag[0].text else None  # 태그 텍스트 추출 (공백 제거)
      time = time_tag[0].text.strip() if time_tag and time_tag[0].text else None
      
      if url and title:
        links.append({'url': url, 'title': title, 'time': time})
    
  return links

# ✅ 여러 HTML 파일에서 URL과 제목을 추출
def process_multiple_html_files(directory, file_pattern='bookmarks-*.html'):
  """
  주어진 디렉터리에서 여러 HTML 파일을 읽고 URL과 제목을 추출합니다.
  """
  all_links = []  # 모든 링크를 저장할 리스트
  
  # 파일 패턴에 맞는 모든 HTML 파일 찾기
  file_paths = glob.glob(os.path.join(directory, file_pattern))
  
  for file_path in file_paths:
    print(f"📄 Processing: {file_path}")
    links = extract_links_from_html(file_path)
    all_links.extend(links)  # 추출된 링크를 전체 리스트에 추가
  
  return all_links

# ✅ JSON 파일에서 기존 리스트(old_list) 불러오기
def load_old_list(json_file='output_links.json'):
  """
  기존 JSON 파일을 불러와 old_list로 반환합니다.
  """
  if os.path.exists(json_file):
    with open(json_file, 'r', encoding='utf-8') as file:
      old_list = json.load(file)
      print(f"✅ Loaded {len(old_list)} items from {json_file}")
      return old_list
  else:
    print(f"⚠️ No existing JSON file found at {json_file}. Returning an empty list.")
    return []

# ✅ 결과를 JSON으로 저장
def save_to_json(data, output_file='output_links.json'):
  """
  추출된 URL, 제목, 시간을 JSON 파일로 저장합니다.
  """
  with open(output_file, 'w', encoding='utf-8') as jsonfile:
    json.dump(data, jsonfile, indent=4, ensure_ascii=False)
  
  print(f"✅ Data saved to {output_file}")

# ✅ 메인 실행
if __name__ == '__main__':
  # HTML 파일들이 저장된 디렉터리 경로 설정
  input_directory = './bookmarks'  # 현재 디렉터리
  
  old_links = load_old_list()
  
  # 기존 리스트 결과 출력 (일부만 확인)
  for link in old_links[:5]:
    print(link)
  
  # 여러 HTML 파일 처리
  new_links = process_multiple_html_files(input_directory)
  
  # 새로운 리스트 결과 출력 (일부만 확인)
  for link in new_links[:5]:
    print(link)
  
  # updated_list, removed_items = multiprocessing_global_diff(old_links, new_links)
  updated_list, removed_items = global_diff_update(old_links, new_links)

  print(len(updated_list))
  print(len(removed_items))

  print("✅ 업데이트된 리스트 (일부):", updated_list[:5])
  print("❌ 삭제된 항목 (일부):", removed_items[:5])