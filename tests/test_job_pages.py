"""Regression tests for CareerPick generated ALIO job pages.

Run: python -m unittest discover -s tests -p 'test_job_pages.py'
"""
import unittest

from scripts.build_job_pages import render
from alio import detail_of


class JobPageTests(unittest.TestCase):
    def setUp(self):
        self.post = {
            'id': 'a123456',
            'alio': True,
            'title': '채용 공고 테스트',
            'org': '테스트 기관',
            'due': '2026-12-31',
            'pub': '2026-10-23',
            'emp': '정규직',
            'region': '강원',
            'desc': '실제 담당 업무와 필요한 역량을 안내하는 테스트용 채용공고입니다.',
            'src': 'https://example.org/jobs/123',
        }

    def test_alio_collection_preserves_long_original_detail(self):
        original = '지원자격 상세 ' * 600
        collected = detail_of({'aplyQlfcCn': original})
        self.assertEqual(collected['aplyQlfcCn'], original)
        html = render(self.post, collected)
        self.assertIn('이 항목은 원문이 길어 일부만 표시됩니다', html)

    def test_mobile_layout_and_keyboard_navigation(self):
        html = render(self.post, {})
        self.assertIn('class="skip-link" href="#job-summary"', html)
        self.assertIn('<h2 id="job-summary">모집 요약</h2>', html)
        self.assertIn('a:focus-visible', html)
        self.assertIn('.apply{display:block;text-align:center', html)
        self.assertIn('box-sizing:border-box', html)

    def test_detail_content_and_official_link(self):
        html = render(self.post, {
            'aplyQlfcCn': '관련 자격증 필수',
            'scrnprcdrMthdExpln': '서류 심사 후 면접',
            'prefCn': '국가유공자 우대',
            'prefCondCn': '관련 경력 우대',
        })
        self.assertIn('지원 전 핵심 확인사항', html)
        self.assertIn('관련 자격증 필수', html)
        self.assertIn('서류 심사 후 면접', html)
        self.assertIn('<h2>전형 절차</h2>', html)
        self.assertIn('국가유공자 우대', html)
        self.assertIn('관련 경력 우대', html)
        self.assertIn('https://example.org/jobs/123', html)
        self.assertIn('관련 취업 준비 자료', html)
        self.assertNotIn('<h2>지원 전 체크리스트</h2>', html)
        self.assertNotIn('<h2>공고 핵심정보</h2>', html)

    def test_official_link_explains_application_site_difference(self):
        html = render(self.post, {})
        self.assertIn('공식 원문 및 지원 방법 확인', html)
        self.assertIn('별도의 채용 접수 사이트로 이동해야 할 수 있습니다', html)
        self.assertIn('공식 채용공고 열기', html)
        self.assertIn('rel="noopener noreferrer"', html)

    def test_missing_official_link_has_no_false_apply_button(self):
        post = dict(self.post)
        post.pop('src', None)
        post.pop('url', None)
        html = render(post, {})
        self.assertIn('공식 링크를 확인할 수 없습니다', html)
        self.assertNotIn('공식 채용공고 열기', html)

    def test_repeated_alio_title_not_rendered_as_detail(self):
        html = render(self.post, {
            'recrutPblntTtl': '채용 공고 테스트',
            'recrutSeNm': '신입',
            'aplyQlfcCn': '자격증 필수',
        })
        self.assertEqual(html.count('<h1>채용 공고 테스트</h1>'), 1)
        self.assertNotIn('<h2>채용공고 제목</h2>', html)
        self.assertIn('<h2>채용 구분</h2>', html)
        self.assertIn('<h2>지원 자격</h2>', html)

    def test_multiline_details_preserved(self):
        html = render(self.post, {
            'aplyQlfcCn': '1. 필수 조건\\n2. 우대 조건',
        })
        self.assertIn('class="detail-text"', html)
        self.assertIn('1. 필수 조건\\n2. 우대 조건', html)
        self.assertIn('white-space:pre-wrap', html)

    def test_long_official_detail_is_not_silently_cut_at_1500(self):
        detail = '지원 자격 안내 ' * 150
        html = render(self.post, {'aplyQlfcCn': detail})
        self.assertIn(detail, html)
        self.assertNotIn('이 항목은 원문이 길어 일부만 표시됩니다', html)

    def test_very_long_official_detail_has_explicit_truncation_notice(self):
        detail = '자격 조건 ' * 1200
        html = render(self.post, {'aplyQlfcCn': detail})
        self.assertIn('이 항목은 원문이 길어 일부만 표시됩니다', html)
        self.assertIn('전체 내용은 반드시 공식 채용공고에서 확인하세요', html)

    def test_disqualification_field_is_rendered(self):
        html = render(self.post, {'disqlfcRsn': '결격사유 원문 확인'})
        self.assertIn('<h2>결격사유</h2>', html)
        self.assertIn('결격사유 원문 확인', html)

    def test_disqualification_field_is_not_fabricated(self):
        html = render(self.post, {})
        self.assertNotIn('<h2>결격사유</h2>', html)

    def test_missing_details_are_not_invented(self):
        html = render(self.post, {})
        self.assertIn('상세 자격·전형 데이터가 제공되지 않았습니다', html)
        self.assertNotIn('관련 자격증 필수', html)

    def test_ncs_classification_alone_does_not_imply_written_exam(self):
        post = dict(self.post, title='공공기관 NCS 직무 채용', desc='NCS 경영·사무 직무 분류')
        html = render(post, {'scrnprcdrMthdExpln': '서류전형 후 면접'})
        self.assertNotIn('NCS 4주 학습 계획', html)

    def test_ncs_written_exam_in_selection_process_shows_guide(self):
        html = render(self.post, {'scrnprcdrMthdExpln': '서류심사 → NCS 직업기초능력 필기시험 → 면접'})
        self.assertIn('NCS 4주 학습 계획', html)

    def test_generic_written_exam_does_not_imply_ncs(self):
        html = render(self.post, {'scrnprcdrMthdExpln': '서류심사 → 전공 필기시험 → 면접'})
        self.assertNotIn('NCS 4주 학습 계획', html)

    def test_ncs_assessment_in_document_screening_not_written_exam(self):
        html = render(self.post, {'scrnprcdrMthdExpln': '1. 서류전형\\n- 평가: 직업기초능력(40%)\\n2. 면접전형\\n- 평가: 직업기초역량(40%)'})
        self.assertNotIn('NCS 4주 학습 계획', html)

    def test_ncs_exam_on_next_line_is_detected(self):
        html = render(self.post, {'scrnprcdrMthdExpln': '2차 : 필기전형\\n- 직무공통능력검사(NCS - 의사소통능력, 문제해결능력)\\n3차 : 면접전형'})
        self.assertIn('NCS 4주 학습 계획', html)

    def test_ncs_assessment_in_written_exam_section(self):
        html = render(self.post, {'scrnprcdrMthdExpln': '다. 필기전형\\n - NCS직업 기초능력\\n - 인성검사\\n라. 면접전형'})
        self.assertIn('NCS 4주 학습 계획', html)

    def test_long_ncs_classification_is_not_presented_as_job_duties(self):
        post = dict(
            self.post,
            desc='경영·회계·사무 · 총무·인사 · 재무·회계 · 사무행정 · '
                 '경영기획 · 일반사무 · 기타 공공기관 직무 분류',
        )
        html = render(post, {'aplyQlfcCn': '지원 가능'})
        self.assertIn('<h2>직무 분류</h2>', html)
        self.assertIn('직무 분류는 실제 담당업무 설명이 아닙니다', html)
        self.assertNotIn('<h2>공고 세부 요약</h2>', html)
        self.assertIn('공식 원문에서 추가 확인할 항목: 상세 직무 설명', html)

    def test_html_escaping(self):
        post = dict(self.post, title='<script>alert(1)</script>')
        html = render(post, {})
        self.assertIn('&lt;script&gt;alert(1)&lt;/script&gt;', html)
        self.assertNotIn('<h1><script>', html)


if __name__ == '__main__':
    unittest.main()
