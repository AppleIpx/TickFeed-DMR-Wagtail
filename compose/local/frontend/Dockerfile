FROM docker.io/node:24.21-alpine

ARG APP_HOME=/app

WORKDIR ${APP_HOME}

COPY ./frontend/package.json ./frontend/package-lock.json ${APP_HOME}/

RUN --mount=type=cache,target=/root/.npm \
    npm ci && cp package-lock.json node_modules/.install-stamp

COPY ./compose/local/frontend/start /start
RUN sed -i 's/\r$//g' /start
RUN chmod +x /start

EXPOSE 3000

CMD ["/start"]
