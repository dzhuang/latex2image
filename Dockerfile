FROM python:3.7.7-slim-buster
MAINTAINER Dong Zhuang <dzhuang.scut@gmail.com>

COPY ["latex2image", "texlive_apt.list", "/opt/latex2image/"]
COPY extra_fonts /usr/share/fonts/extra_fonts

RUN apt-get update \
    && apt-get install -y --no-install-recommends -qq nginx imagemagick curl git memcached $(awk '{print $1'} /opt/latex2image/texlive_apt.list) \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && yes | rm /etc/ImageMagick*/policy.xml \
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
