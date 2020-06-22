FROM python:3.7.7-slim-buster
MAINTAINER Dong Zhuang <dzhuang.scut@gmail.com>

COPY ["latex2image", "texlive_apt.list", "/opt/latex2image/"]
COPY extra_fonts /usr/share/fonts/extra_fonts

RUN apt-get update \
    && apt-get install -y --no-install-recommends -qq nginx imagemagick curl git memcached unzip $(awk '{print $1'} /opt/latex2image/texlive_apt.list) \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && yes | rm /etc/ImageMagick*/policy.xml \
    && mkdir -p /usr/share/fonts/extra_fonts \
    && mkdir -p /usr/share/fonts/otf \
    && curl -sS "https://raw.githubusercontent.com/adobe-fonts/source-han-serif/release/SubsetOTF/SourceHanSerifCN.zip" -o SourceHanSerifCN.zip \
    && unzip -p SourceHanSerifCN.zip \
    && mv SourceHanSerifCN/*.otf /usr/share/fonts/otf \
    && rm -f SourceHanSerifCN.zip \
    && curl -sS "https://raw.githubusercontent.com/adobe-fonts/source-han-sans/release/SubsetOTF/SourceHanSansCN.zip" -o SourceHanSansCN.zip \
    && unzip -pq SourceHanSansCN.zip \
    && mv SourceHanSansCN/*.otf /usr/share/fonts/otf \
    && rm -f SourceHanSansCN.zip \
    && curl -sS "https://github.com/yukai-w/yukai-w.github.io/blob/master/FZKTJW.TTF?raw=true" -o /usr/share/fonts/truetype/FZKTJW.TTF \
    && fc-cache -f

COPY nginx.default /etc/nginx/sites-available/default
WORKDIR /opt/latex2image/
RUN ln -sf /dev/stdout /var/log/nginx/access.log \
    && ln -sf /dev/stderr /var/log/nginx/error.log \
    && echo gunicorn >> requirements.txt \
    && pip install --no-cache-dir -r requirements.txt \
    && mkdir -p /opt/latex2image/tmp \
    && chown -R www-data:www-data /opt/latex2image

VOLUME /opt/latex2image/local_settings

# Fix lualatex https://github.com/overleaf/overleaf/pull/739/files
ENV TEXMFVAR=/opt/latex2image/tmp

EXPOSE 8020

# Start server
STOPSIGNAL SIGTERM
CMD ["/opt/latex2image/start-server.sh"]
