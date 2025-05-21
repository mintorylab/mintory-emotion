from flask import Flask, request, jsonify, send_from_directory
from youtube_transcript_api import YouTubeTranscriptApi
import openai
import anthropic
import os
import json
from datetime import datetime
from flask_cors import CORS

app = Flask(__name__, static_folder='public', static_url_path='')
CORS(app)

# API 키 설정
openai.api_key = "sk-temp-key"  # 임시 키
# claude = anthropic.Anthropic(api_key="sk-ant-temp-key")  # 임시 키 - 주석 처리

# 결과 저장 디렉토리 생성
RESULTS_DIR = "analysis_results"
if not os.path.exists(RESULTS_DIR):
    os.makedirs(RESULTS_DIR)

# 더미 데이터
DUMMY_RESULT = {
    "timestamp": "2024-05-21T12:00:00Z",
    "style": "팩폭형",
    "emotions": [
        {"name": "희망", "percentage": 45},
        {"name": "열정", "percentage": 30},
        {"name": "공감", "percentage": 25}
    ],
    "analysis": "영상은 희망적인 메시지를 강조하며 청자에게 강한 동기부여를 주고 있습니다.",
    "feedback": "팩폭을 사용할 때는 마무리에 따뜻한 위로를 함께 담는 것이 중요합니다."
}

@app.route("/")
def home():
    return send_from_directory("public", "index.html")

@app.route("/upload.html")
def upload():
    return send_from_directory("public", "upload.html")

@app.route("/result.html")
def result():
    return send_from_directory("public", "result.html")

@app.route("/combined-result.html")
def combined_result():
    return send_from_directory("public", "combined-result.html")

def get_video_id(url):
    if "watch?v=" in url:
        return url.split("watch?v=")[1].split("&")[0]
    elif "youtu.be/" in url:
        return url.split("youtu.be/")[1].split("?")[0]
    else:
        return None

def get_transcript(video_url):
    video_id = get_video_id(video_url)
    if not video_id:
        return None
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['ko', 'en'])
        full_text = " ".join([entry['text'] for entry in transcript])
        return full_text
    except:
        return None

def analyze_with_chatgpt(text, style="comfort"):
    style_prompts = {
        "fact": """
        다음 유튜브 영상 자막을 날카롭고 직설적으로 분석해주세요:

        1. 감정 요약 (직설적으로 2-3문장)
        2. 문제점 지적 (가장 큰 문제 3가지)
        3. 개선을 위한 피드백 (단도직입적인 조언)

        자막 내용:
        {text}
        """,
        
        "insight": """
        다음 유튜브 영상 자막을 심층적으로 분석해주세요:

        1. 감정 패턴 분석 (2-3문장)
        2. 감정의 근본 원인 탐색
        3. 심리학적 통찰과 제안

        자막 내용:
        {text}
        """,
        
        "comfort": """
        다음 유튜브 영상 자막을 따뜻하고 공감적인 시각으로 분석해주세요:

        1. 감정 상태 공감 (2-3문장)
        2. 긍정적인 측면 발견
        3. 따뜻한 위로와 격려

        자막 내용:
        {text}
        """
    }

    prompt = style_prompts.get(style, style_prompts["comfort"]).format(text=text[:3000])
    
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "당신은 영상 콘텐츠의 감정과 심리를 분석하는 전문가입니다."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=1000
    )

    return response['choices'][0]['message']['content']

def analyze_emotions_with_claude(text):
    prompt = f"""
    다음은 유튜브 영상의 자막입니다. 이 내용에서 감지되는 주요 감정들을 분석하고, 각 감정의 비율(%)을 계산해주세요.
    결과는 반드시 다음과 같은 JSON 형식으로 출력해주세요:

    {{
        "emotions": [
            {{"name": "감정1", "percentage": 비율}},
            {{"name": "감정2", "percentage": 비율}},
            {{"name": "감정3", "percentage": 비율}}
        ]
    }}

    - 감정은 3개로 추출해주세요
    - 비율의 총합은 100이 되어야 합니다
    - 가장 강한 감정부터 순서대로 나열해주세요

    자막 내용:
    {text[:3000]}
    """

    response = claude.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=1000,
        temperature=0.7,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return json.loads(response.content[0].text)

@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        data = request.get_json()
        video_url = data.get("videoUrl")
        
        if not video_url:
            return jsonify({"error": "URL이 제공되지 않았습니다."}), 400
            
        # 더미 데이터 반환
        return jsonify(DUMMY_RESULT)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/get-latest-result")
def get_latest_result():
    # 더미 데이터 반환
    return jsonify(DUMMY_RESULT)

@app.route("/analyze-recent", methods=["POST"])
def analyze_recent():
    try:
        # 최근 3개 파일 가져오기
        files = os.listdir(RESULTS_DIR)
        if not files:
            return jsonify({"error": "분석된 영상이 없습니다."}), 404

        # 최근 순으로 정렬하여 3개 선택
        recent_files = sorted(files, 
                            key=lambda x: os.path.getctime(os.path.join(RESULTS_DIR, x)), 
                            reverse=True)[:3]
        
        # 각 파일의 결과 읽기
        results = []
        for file in recent_files:
            with open(os.path.join(RESULTS_DIR, file), 'r', encoding='utf-8') as f:
                results.append(json.load(f))

        # 통합 분석을 위한 텍스트 준비
        combined_text = "\n\n".join([
            f"영상 {i+1}의 분석:\n{result['analysis']}" 
            for i, result in enumerate(results)
        ])

        # 모든 감정 데이터 수집
        all_emotions = []
        for result in results:
            all_emotions.extend(result['emotions'])

        # 감정 통합 및 평균 계산
        emotion_sums = {}
        for emotion in all_emotions:
            if emotion['name'] not in emotion_sums:
                emotion_sums[emotion['name']] = {'total': 0, 'count': 0}
            emotion_sums[emotion['name']]['total'] += emotion['percentage']
            emotion_sums[emotion['name']]['count'] += 1

        # 평균 감정 비율 계산 및 상위 3개 선택
        averaged_emotions = [
            {
                'name': name,
                'percentage': round(data['total'] / data['count'], 1)
            }
            for name, data in emotion_sums.items()
        ]
        averaged_emotions.sort(key=lambda x: x['percentage'], reverse=True)
        top_emotions = averaged_emotions[:3]

        # 총합이 100이 되도록 조정
        total = sum(emotion['percentage'] for emotion in top_emotions)
        for emotion in top_emotions:
            emotion['percentage'] = round((emotion['percentage'] / total) * 100, 1)

        # Claude를 사용하여 통합 인사이트 생성
        insight_prompt = f"""
        다음은 3개의 영상에 대한 감정 분석 결과입니다. 이를 통합적으로 분석하여 다음 형식으로 답변해주세요:

        1. 전반적인 감정 패턴
        2. 시청자의 심리 상태 추정
        3. 앞으로의 컨텐츠 방향성 제안
        4. 전문가의 조언

        분석 내용:
        {combined_text}
        """

        insight_response = claude.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=1000,
            temperature=0.7,
            messages=[
                {"role": "user", "content": insight_prompt}
            ]
        )

        # 결과 저장
        result = {
            "timestamp": datetime.now().isoformat(),
            "type": "combined_analysis",
            "emotions": top_emotions,
            "individual_results": [
                {
                    "url": r["video_url"],
                    "timestamp": r["timestamp"]
                } for r in results
            ],
            "combined_insight": insight_response.content[0].text
        }

        # 통합 분석 결과 저장
        filename = f"{RESULTS_DIR}/combined_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

        return jsonify(result)

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=8000)
