ARG NODE_IMAGE=node@sha256:ebfe2f90462722a7a4de65e91990e97fe0d401c70e0e762c5b53302f905ec1c1
FROM ${NODE_IMAGE}
WORKDIR /app
COPY --chown=node:node frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY --chown=node:node frontend/index.html frontend/tsconfig.json frontend/vite.config.ts ./
COPY --chown=node:node frontend/src ./src
USER node
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173", "--strictPort"]
