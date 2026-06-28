FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 express && \
    mkdir -p /app/uploads && \
    chown -R express:nodejs /app/uploads
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY package.json ./
USER express
EXPOSE 4000
ENV NODE_ENV=production
CMD ["node", "dist/index.js"]
