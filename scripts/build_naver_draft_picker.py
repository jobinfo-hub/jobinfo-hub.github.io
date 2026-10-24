"""Generate a self-contained, offline Naver draft picker from the review-only archive."""
import html
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DRAFTS = ROOT / "naver-drafts"
OUTPUT = ROOT / "naver-review-packs" / "index.html"

def main():
    manifest = json.loads((DRAFTS / "manifest.json").read_text(encoding="utf-8"))
    entries = []
    for item in manifest:
        pid = item["id"]
        text = (DRAFTS / item["file"]).read_text(encoding="utf-8")
        heading = text.splitlines()[0].removeprefix("# ").strip()
        entries.append({
            "id": pid, "title": heading, "body": text,
            "expired": bool(item["expired"]),
            "deadline_known": bool(item["deadline_known"]),
            "thumbnail": pid + "-thumbnail.png",
        })
    # Escape <, > and & in embedded JSON so ALIO titles cannot inject markup.
    payload = json.dumps(entries, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    page = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>커리어픽 | 네이버 블로그 초안 선택</title>
<style>
body{font:16px/1.6 system-ui,sans-serif;margin:0;background:#f4f7fb;color:#172b4d}
main{max-width:1050px;margin:auto;padding:22px}
h1{font-size:25px} input,select,button{font:inherit;padding:11px;border:1px solid #b8c8d9;border-radius:9px}
input{width:min(100%,460px);box-sizing:border-box}
button{background:#123e79;color:white;cursor:pointer}
.controls{display:flex;flex-wrap:wrap;gap:9px;margin:15px 0}
.layout{display:grid;grid-template-columns:minmax(220px,1fr) minmax(300px,2fr);gap:18px}
#results{max-height:68vh;overflow:auto;background:white;border-radius:12px;padding:8px}
#results button{display:block;text-align:left;width:100%;margin:5px 0;background:#f2f6fc;color:#172b4d}
article{background:white;border-radius:12px;padding:18px;min-width:0}
pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:56vh;overflow:auto}
img{max-width:220px;width:100%}
small{color:#56677d}
@media(max-width:720px){.layout{grid-template-columns:1fr}#results{max-height:240px}}
</style></head><body><main>
<h1>커리어픽 · 네이버 블로그 초안 선택기</h1>
<p>전체 ALIO 초안 검색·선택·복사 도구입니다. 네이버 로그인이나 자동 발행은 하지 않습니다. 게시 전 반드시 원문을 검수하세요.</p>
<div class="controls"><input id="search" placeholder="기관명·제목 검색" aria-label="공고 검색">
<select id="filter" aria-label="마감 상태"><option value="all">전체</option><option value="active">마감 표시 없음</option><option value="expired">마감 공고</option><option value="unknown">마감일 미확인</option></select>
<span id="count" aria-live="polite"></span></div>
<div class="layout"><div id="results"></div><article>
<h2 id="title">공고를 선택하세요</h2><small id="status"></small>
<div class="controls"><button id="copytitle">제목 복사</button><button id="copybody">본문 복사</button>
<a id="thumbnail" download="thumbnail.png">썸네일 열기·저장</a></div>
<pre id="body"></pre>
</article></div><p><small>검수 필요: 공식 모집요강·접수시간·지원자격 확인 후 네이버 에디터에서 임시저장하세요.</small></p>
<script id="drafts-data" type="application/json">__PAYLOAD__</script>
<script>
const items=JSON.parse(document.getElementById('drafts-data').textContent);
let selected=null;
const $=id=>document.getElementById(id);
function choose(item){
 selected=item;$('title').textContent=item.title;$('body').textContent=item.body;
 $('status').textContent=item.expired?'마감 공고 · 기록용':(!item.deadline_known?'마감일 확인 필요':'모집 여부 원문 확인 필요');
 $('thumbnail').href=item.thumbnail;$('thumbnail').download=item.thumbnail;
}
function render(){
 const q=$('search').value.trim().toLowerCase(),filter=$('filter').value;
 const found=items.filter(x=>x.title.toLowerCase().includes(q)&&
 (filter==='all'||(filter==='expired'&&x.expired)||(filter==='unknown'&&!x.deadline_known)||(filter==='active'&&!x.expired)));
 $('count').textContent=found.length+' / '+items.length+'개';
 $('results').replaceChildren();
 for(const item of found.slice(0,250)){
 const b=document.createElement('button');b.textContent=item.title;b.onclick=()=>choose(item);$('results').appendChild(b);
 }
 if(found.length>250){const p=document.createElement('p');p.textContent='검색 결과가 많아 상위 250개만 표시합니다. 검색어를 좁혀주세요.';$('results').appendChild(p);}
}
$('search').addEventListener('input',render);$('filter').addEventListener('change',render);
$('copytitle').onclick=()=>selected&&navigator.clipboard.writeText(selected.title);
$('copybody').onclick=()=>selected&&navigator.clipboard.writeText(selected.body);
render();if(items.length)choose(items[0]);
</script></main></body></html>"""
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(page.replace("__PAYLOAD__", payload), encoding="utf-8")
    print(f"Built offline Naver draft picker with {len(entries)} entries: {OUTPUT}")

if __name__ == "__main__":
    main()
