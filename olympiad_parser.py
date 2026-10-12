import requests
from bs4 import BeautifulSoup


def get_olympiads_from_web():
    url = "https://olimpiada.ru/activities"

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        olympiads_list = []
        h2_tags = soup.find_all('h2', limit=15)

        for h2 in h2_tags:
            title = h2.text.strip()

            link_tag = h2.find('a') or h2.find_parent('a')

            if link_tag and link_tag.get('href'):
                href = link_tag['href']
                link = "https://olimpiada.ru" + href if href.startswith('/') else href
            else:
                link = "https://olimpiada.ru/activities"

            if len(title) > 10:
                olympiads_list.append({
                    'title': title,
                    'link': link,
                    'source': 'olimpiada.ru'
                })

        if not olympiads_list:
            return get_fallback_olympiads()

        return olympiads_list

    except Exception as e:
        print("Не удалось скачать олимпиады. Ошибка:", e)
        return get_fallback_olympiads()


def get_fallback_olympiads():
    return [
        {
            'title': 'Всероссийская олимпиада школьников (ВсОШ) - Текущий этап',
            'link': 'https://vserosolimp.edsoo.ru/',
            'source': 'Официальный сайт ВсОШ (резерв)'
        },
        {
            'title': 'Московская олимпиада школьников',
            'link': 'https://mos.olimpiada.ru/',
            'source': 'Официальный сайт (резерв)'
        },
        {
            'title': 'Олимпиада «Высшая проба»',
            'link': 'https://olymp.hse.ru/',
            'source': 'Официальный сайт (резерв)'
        }
    ]