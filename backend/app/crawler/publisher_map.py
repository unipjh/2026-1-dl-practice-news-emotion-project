PUBLISHER_MAP = {
    # 종합일간지
    "chosun.com": "조선일보",
    "donga.com": "동아일보",
    "hani.co.kr": "한겨레",
    "khan.co.kr": "경향신문",
    "joongang.co.kr": "중앙일보",
    "joins.com": "중앙일보",
    "ohmynews.com": "오마이뉴스",
    "pressian.com": "프레시안",
    "hankookilbo.com": "한국일보",
    # 방송
    "kbs.co.kr": "KBS",
    "imnews.imbc.com": "MBC",
    "mbc.co.kr": "MBC",
    "sbs.co.kr": "SBS",
    "jtbc.co.kr": "JTBC",
    "ytn.co.kr": "YTN",
    "mbn.co.kr": "MBN",
    "tvchosun.com": "TV조선",
    # 통신사
    "yna.co.kr": "연합뉴스",
    "newsis.com": "뉴시스",
    "news1.kr": "뉴스1",
    # 경제지
    "hankyung.com": "한국경제",
    "mt.co.kr": "머니투데이",
    "edaily.co.kr": "이데일리",
    "mk.co.kr": "매일경제",
    "biz.chosun.com": "조선비즈",
    "heraldcorp.com": "헤럴드경제",
    "sedaily.com": "서울경제",
    "fnnews.com": "파이낸셜뉴스",
    # 인터넷 매체
    "newspim.com": "뉴스핌",
    "nocutnews.co.kr": "노컷뉴스",
    "mediatoday.co.kr": "미디어오늘",
}


def identify_publisher(url: str) -> str:
    for domain, name in PUBLISHER_MAP.items():
        if domain in url:
            return name
    return "기타"
