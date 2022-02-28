ARG base

FROM ${base}

ARG USERNAME=l2i_user

COPY --chown=$USERNAME latex2image /opt/latex2image/

WORKDIR /opt/latex2image/
VOLUME /opt/latex2image/local_settings
VOLUME /var/log/nginx

# Fix lualatex https://github.com/overleaf/overleaf/pull/739/files
ENV TEXMFVAR=/opt/latex2image/tmp

USER $USERNAME

EXPOSE 8020

# Start server
STOPSIGNAL SIGTERM
CMD ["/opt/latex2image/start-server.sh"]
