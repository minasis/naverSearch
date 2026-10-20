"""네이버 카페 검색 & 엑셀 수집기 Flask 경량 웹 애플리케이션."""

import os
import re
from datetime import datetime, timezone, timedelta
from flask import Flask, request, jsonify, render_template, send_from_directory, abort

from crawler_engine import search_and_collect, validate_date_range

app = Flask(__name__)

KST = timezone(timedelta(hours=9))

# 엑셀 파일 저장 디렉터리 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOAD_FOLDER = os.path.join(BASE_DIR, "downloads")
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)


@app.route("/")
def index():
    """메인 검색 페이지 렌더링."""
    return render_template("index.html")


@app.route("/api/search", methods=["POST"])
def api_search():
    """기간별 네이버 카페 검색 및 REA 엑셀 수집 API."""
    data = request.get_json(silent=True) or {}
    query = (data.get("query") or "").strip()
    start_date = (data.get("start_date") or "").strip()
    end_date = (data.get("end_date") or "").strip()

    if not query:
        return jsonify({"success": False, "error": "검색어를 입력해 주세요."}), 400

    if not start_date or not end_date:
        return jsonify({"success": False, "error": "시작일과 종료일을 모두 입력해 주세요."}), 400

    try:
        start_dt, end_dt = validate_date_range(start_date, end_date, max_days=5)
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400

    try:
        # 크롤링 및 거래글 필터링 실행
        df = search_and_collect(
            query=query,
            start_date=start_date,
            end_date=end_date,
            max_days=5
        )

        # 안전한 엑셀 파일명 생성
        safe_query = re.sub(r'[\\/*?:"<>| ]+', '_', query)
        timestamp = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
        start_str = start_dt.strftime("%Y%m%d")
        end_str = end_dt.strftime("%Y%m%d")
        filename = f"naver_cafe_{safe_query}_{start_str}_{end_str}_{timestamp}.xlsx"
        file_path = os.path.join(DOWNLOAD_FOLDER, filename)

        # 엑셀 파일 저장
        df.to_excel(file_path, index=False, engine="openpyxl")

        attrs = getattr(df, "attrs", {})
        summary = {
            "query": query,
            "start_date": attrs.get("start_date", start_dt.strftime("%Y-%m-%d")),
            "end_date": attrs.get("end_date", end_dt.strftime("%Y-%m-%d")),
            "total_candidates": int(attrs.get("total_candidates", len(df))),
            "trade_excluded": int(attrs.get("trade_excluded", 0)),
            "valid_count": int(attrs.get("valid_count", len(df))),
            "filename": filename,
            "download_url": f"/api/download/{filename}"
        }

        # 상위 10건 미리보기 데이터 추출
        preview_rows = df.head(10).to_dict(orient="records")

        return jsonify({
            "success": True,
            "summary": summary,
            "preview": preview_rows
        }), 200

    except Exception as e:
        return jsonify({"success": False, "error": f"수집 중 오류 발생: {str(e)}"}), 500


@app.route("/api/download/<filename>")
def api_download(filename: str):
    """생성된 엑셀 파일 다운로드 엔드포인트."""
    # 디렉터리 탐색(Traversal) 방지 보안 검증
    if not filename or ".." in filename or "/" in filename or "\\" in filename:
        abort(400, description="잘못된 파일 요청입니다.")

    safe_name = os.path.basename(filename)
    file_path = os.path.join(DOWNLOAD_FOLDER, safe_name)

    if not os.path.isfile(file_path):
        abort(404, description="요청한 파일을 찾을 수 없습니다.")

    return send_from_directory(
        DOWNLOAD_FOLDER,
        safe_name,
        as_attachment=True,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
