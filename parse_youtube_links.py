# beautiful soup for HTML parsing
import json
import os
import re
import urllib.parse

import requests
from bs4 import BeautifulSoup


def get_page_number_from_url(last_post):
    if not last_post:
        return ''
    regex_page = re.compile("page=([0-9]{1,2})")
    m_pg = regex_page.search(last_post)
    if m_pg:
        return m_pg.group(1)
    return ''


class VBulletinVideoCrawler:

    def __init__(self, login_url='', login_data={}):
        self.__login_url = login_url
        self.__login_data = login_data
        self.__session_started = False
        self.__session = None
        self.__start_url = ''
        self.__page_number = ''
        self.__base_url = ''
        self.__thread_id = ''
        self.__current_post_url = ''
        self.__current_post_offset = ''
        self.__current_post_number = ''
        self.__current_post_date = ''
        self.__current_post_author = ''
        self.__current_post_author_profile = ''
        self.__last_message_parsed = ''
        self.__last_modified_date = ''
        # README
        # The standard Python dict does this by default if you're using CPython 3.6+
        # (or Python 3.7+ for any other implementation of Python).
        # On older versions of Python you can use collections.OrderedDict.
        self.__video_dict = {}
        self.__thread_name = ''

    @property
    def video_dict(self):
        return self.__video_dict

    @property
    def thread_name(self):
        return self.__thread_name

    @property
    def last_parsed_message(self):
        return self.__last_message_parsed

    def check_thread_is_updated(self, thread_url, last_mod_date_from_db):
        """

        :param thread_url:
        :param last_mod_date_from_db:  if empty it means thread was not parsed before
        :return: True if we detect last modified date of thread is not the same as the one stored in db
        """
        if not self.__last_modified_date:
            self.get_thread_name_from_url(thread_url)
        return (not last_mod_date_from_db) or (self.__last_modified_date != last_mod_date_from_db)

    def _get_soup_from_url(self, url):
        if not self.__session:
            self.__session = requests.Session()
        current_page = self.__session.get(url)
        if current_page.status_code != requests.codes.ok:
            return ''
        if self.check_private_thread(current_page, url):
            # tengo que actualizar current_page a un valor adecuado
            current_page = self.__session.get(url)
        soup = BeautifulSoup(current_page.text, features="html.parser")
        return soup

    def get_last_modification_date(self, url=''):
        if self.__last_modified_date:
            return self.__last_modified_date
        self.parse_thread_name_and_modified_date(self._get_soup_from_url(url))
        return self.__last_modified_date

    def get_thread_name_from_url(self, url):
        if self.__thread_name:
            return self.__thread_name
        self.parse_thread_name_and_modified_date(self._get_soup_from_url(url))
        return self.__thread_name

    def start_parsing(self, start_url, last_post='', last_mod_date=''):
        if not start_url:
            print('No thread url defined')
            return
        if not self.__session:
            self.__session = requests.Session()
        path = urllib.parse.urlparse(start_url)
        self.__base_url = path.scheme + '://' + path.netloc + '/'
        path_split = os.path.split(path.path)
        self.__base_url += path_split[0] + '/'
        regex_id = re.compile("t=([0-9]+)")
        m = regex_id.search(path.query)
        self.__current_post_offset = last_post
        if m:
            self.__thread_id = m.group(1)
        if last_post:
            self.__start_url = start_url + '&' + last_post
            self.__page_number = get_page_number_from_url(last_post)
        else:
            self.__start_url = start_url
            self.__page_number = '1'
        if self.check_thread_is_updated(thread_url=start_url, last_mod_date_from_db=last_mod_date):
            self.parse_thread(self.__start_url)
        self.__last_message_parsed = self.__current_post_offset
        return self.__video_dict

    def add_video_by_url(self, vid_url):
        # check embed
        video_id = ''
        if vid_url.find('embed'):
            # src="//www.youtube.com/embed/6MVGhGdpdDI"
            regex_id = re.compile("embed/([^\"&?\\\/]{11})")
            m = regex_id.search(vid_url)
            if m:
                video_id = m.group(1)
        else:
            # watch?v=z81virrz6TY
            regex_id = re.compile("watch\?v=([^\"&?\\\/]{11})")
            m = regex_id.search(vid_url)
            if m:
                video_id = m.group(1)
        if video_id:
            self.add_video_by_id(vid_id=video_id)

    def add_video_by_id(self, vid_id):
        # check embed
        # FIXME best store just video id and not URL. youtube api works with ids and I have to extract it again
        vid_url = 'https://www.youtube.com/watch?v=' + vid_id
        video_info = {
            'url': vid_url,
            'post_id': self.__current_post_number,
            'post_link': self.__current_post_url,
            'post_offset': self.__current_post_offset,
            'date': self.__current_post_date,
            'author': self.__current_post_author
        }
        if self.__video_dict.get(vid_id):
            return
        else:
            self.__video_dict[vid_id] = video_info

    def find_next(self, soup):
        """
        <div class="pagenav" align="right">
        <table class="tborder" cellspacing="1" cellpadding="3" border="0">
        <tbody>
            <tr>
                <td class="alt1">
                    <a  rel="next"
                        class="smallfont"
                        href="showthread.php?t=8142569&amp;page=2"
                        title="Próxima Página - Resultados del 31 al 60 de 820">&gt;
                    </a>
                </td> <- página siguiente
        """
        pagenav_div = soup.find_all("div", class_="pagenav")
        for div in pagenav_div:
            lista_paginas = div.findChildren("td", class_="alt1", recursive=True)
            # next link is usually second to last (but not always)
            for pagina in reversed(lista_paginas):
                pag_sig = pagina.find("a", {"rel": "next"})
                if pag_sig:
                    next_url = pag_sig.get('href')
                    next_page_number = get_page_number_from_url(next_url)
                    # vBulletin error: sometimes "Next" link returns current URL -> infinite loop
                    if next_page_number and (next_page_number != self.__page_number):
                        self.__page_number = next_page_number
                        return self.__base_url + next_url
                    else:
                        return None
        return None

    def parse_post_children_youtube_iframe(self, content_div):
        """
            <div id="4561" align="center">
                <div class="video-youtube" align="center">
                    <div class="video-container">
                        <iframe title="YouTube video player"
                                class="youtube-player" type="text/html"
                                src="//www.youtube.com/embed/6MVGhGdpdDI"                       <------------ ENLACE
                                allowfullscreen="" width="640" height="390" frameborder="0">
                        </iframe>
                    </div>
                </div>
            </div>
        """
        div_children_embedded_yt = content_div.find_all('div', {'id': re.compile('[0-9]+')})
        if len(div_children_embedded_yt) == 1:
            return
        for div in div_children_embedded_yt:
            # find child with <div class ="video-youtube" align="center" >
            video_div = div.find('div', class_="video-youtube")
            if video_div:
                yt_iframe = video_div.find('iframe', class_="youtube-player", recursive=True)
                video_link = yt_iframe.get('src')
                self.add_video_by_url(video_link)

    def parse_javascript_embed(self, content_div):
        javascript_embed_code = content_div.find_all('script', {'language': 'javascript'}, recursive=False)
        if not javascript_embed_code:
            return
        for embed in javascript_embed_code:
            for content in embed.contents:
                # parse regex: # <!-- # verVideo('6MVGhGdpdDI','4561'); # -->
                regex_id = re.compile("verVideo\(\'([^\"&?\\\/]{11})")
                m = regex_id.search(content)
                if m:
                    id_video = m.group(1)
                    self.add_video_by_id(id_video)

    def parse_raw_links(self, content_div):
        # FIXME regex for shortened links like http://youtu.be/iwGFalTRHDA
        div_children_yt_link = content_div.find_all('a', {'href': re.compile('.*youtube\.com/watch\?v=.*')})
        for yt_link in div_children_yt_link:
            self.add_video_by_url(yt_link.get('href'))

    def parse_post_date_number(self, post_table, post_id):
        link_to_post_num = post_table.find('a', id='postcount'+post_id)
        if link_to_post_num:
            self.__current_post_number = '#' + link_to_post_num.get('name', '')
        first_thead = post_table.find('td', class_='thead')
        if first_thead:
            self.__current_post_date = first_thead.text.strip()

    def parse_post_author(self, post_table):
        # <a class="bigusername" href="member.php?u=012345">user_name</a>
        user_link = post_table.find('a', class_='bigusername')
        self.__current_post_author = user_link.text
        self.__current_post_author_profile = self.__base_url + user_link.get('href')

    def format_post_url(self, id_post):
        self.__current_post_offset = 'page={}#post{}'.format(self.__page_number, id_post)
        self.__current_post_url = '{}showthread.php?t={}&page={}#post{}'.format(self.__base_url,
                                                                                self.__thread_id,
                                                                                self.__page_number,
                                                                                id_post)

    def init_post(self):
        self.__current_post_url = ''
        self.__current_post_number = ''
        self.__current_post_date = ''
        self.__current_post_author = ''
        self.__current_post_author_profile = ''

    def parse_thread_posts(self, current_url, soup):
        # if current_url contains &page=XX#post123456789 i can skip several posts
        skip_limit = ''
        if current_url.find('&page=') != -1:
            skip_regex = re.compile('#post([0-9]+)')
            m = skip_regex.search(current_url)
            if m:
                skip_limit = m.group(1)
        regex_id = re.compile("edit([0-9]{9})")
        all_posts = soup.find_all('div', id=regex_id, recursive=True)
        for post in all_posts:
            self.init_post()
            p_id = post.get('id', '')
            if not p_id:
                continue
            id_post = p_id[-9:]
            if skip_limit:
                if id_post != skip_limit:
                    continue
                else:
                    skip_limit = ''
            post_table = post.find('table', {'id': 'post' + id_post})
            if post_table:
                self.format_post_url(id_post)
                self.parse_post_date_number(post_table, id_post)
                self.parse_post_author(post_table)
                content_div = post_table.find('td', {'id': 'td_post_' + id_post})
                if not content_div:
                    return
                self.parse_post_children_youtube_iframe(content_div)
                self.parse_javascript_embed(content_div)
                self.parse_raw_links(content_div)

    def check_private_thread(self, current_page, current_url):
        if len(current_page.history) > 0:
            if current_page.history[0].status_code == 302:
                # comprobar redirección
                if current_page.url != current_url:
                    print('Redirigido a ' + current_page.url)
                    self.do_login()
                    return self.__session_started
        return True

    def do_login(self):
        self.__session_started = False
        if not self.__session:
            self.__session = requests.Session()
        if not self.__login_url:
            self.__login_url = self.__base_url + 'login.php'
        r = self.__session.post(self.__login_url, data=self.__login_data)
        cookie_bbimloggedin = r.cookies.get('bbimloggedin', default='no')
        if cookie_bbimloggedin == 'yes':
            self.__session_started = True

    def parse_thread(self, thread_url):
        self.__thread_name = ''
        current_url = thread_url
        while current_url:
            current_page = self.__session.get(current_url)
            if current_page.status_code != requests.codes.ok:
                break
            if current_url == thread_url:
                if self.check_private_thread(current_page, current_url):
                    # tengo que actualizar current_page a un valor adecuado
                    current_page = self.__session.get(current_url)
                else:
                    return
            # SoupStrainer
            # https://www.crummy.com/software/BeautifulSoup/bs4/doc/#parsing-only-part-of-a-document
            # only_tags_with_id_link2 = SoupStrainer(id="link2")
            # -> <div id="edit152255703" style="padding:0px 0px 5px 0px">
            soup = BeautifulSoup(current_page.text, features="html.parser")
            self.parse_thread_name_and_modified_date(soup)
            self.parse_thread_posts(current_url, soup)
            # busco el enlace a la página siguiente
            current_url = self.find_next(soup)

    # def parse_thread_name(self, soup):
    #     if not self.__thread_name:
    #         meta = soup.find('meta', {'name': 'description'})
    #         description_str = meta['content']
    #         if description_str.startswith(' '):
    #             self.__thread_name = description_str.strip()
    #         else:
    #             # content="Página 21- JAZZ  LO-FI HIP HOP ,VAPORWAVE BEATS  [...] General"
    #             self.__thread_name = description_str[len("Página 00- "):]

    def parse_thread_name_and_modified_date(self, current_page):
        if self.__last_modified_date and self.__thread_name:
            return
        all_script_data = current_page.find_all('script', {'type': 'application/ld+json'})
        for data in all_script_data:
            data_as_json = json.loads(data.string)
            if data_as_json.get("@type", '') == 'DiscussionForumPosting':
                self.__last_modified_date = data_as_json.get('dateModified', '')
                self.__thread_name = data_as_json.get('headline', '')
                return
