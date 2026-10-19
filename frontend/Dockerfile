# Development image: runs the Vite dev server with hot reload.
# A production image would `npm run build` and serve `dist/` from nginx.
FROM node:24-alpine

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
