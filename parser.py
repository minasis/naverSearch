from bs4 import BeautifulSoup


def parse_cafe_item(bx_elem) -> dict | None:
    """개별 li.bx 요소에서 카페 검색 결과 데이터 추출."""
    title_elem = bx_elem.select_one('a.title_link, a.api_txt_lines.total_tit, a.title')
    if not title_elem:
        return None

    title = title_elem.get_text(strip=True)
    link = title_elem.get('href', '')

    desc_elem = bx_elem.select_one('div.dsc_area, a.dsc_link, div.detail_box, a.api_txt_lines.dsc_txt, .dsc')
    desc = desc_elem.get_text(strip=True) if desc_elem else ""

    cafe_elem = bx_elem.select_one('a.name, .sub_txt.sub_name, .source_txt')
    cafename = cafe_elem.get_text(strip=True) if cafe_elem else ""

    time_elem = bx_elem.select_one('span.sub, span.sub_time, span.txt_inline, .date, .time')
    post_time = time_elem.get_text(strip=True) if time_elem else ""

    return {
        "title": title,
        "link": link,
        "desc": desc,
        "cafename": cafename,
        "post_time": post_time
    }


def parse_cafe_search_results(html_content: str) -> list[dict]:
    """네이버 카페 검색 결과 HTML에서 게시글 목록 파싱."""
    if not html_content:
        return []
    soup = BeautifulSoup(html_content, 'html.parser')
    bx_list = soup.select('li.bx')
    results = []
    for bx in bx_list:
        item = parse_cafe_item(bx)
        if item:
            results.append(item)
    return results
