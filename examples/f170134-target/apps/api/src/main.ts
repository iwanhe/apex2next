import 'reflect-metadata';
import { NestFactory } from '@nestjs/core';
import { AppModule } from './app.module';
import { accessLog } from './http/access-log';

async function bootstrap() {
  const app = await NestFactory.create(AppModule, { cors: false });
  app.enableShutdownHooks();
  if (process.env.ACCESS_LOG !== 'off') app.use(accessLog());
  // The web tier calls this API server-side; bind to loopback unless API_HOST says otherwise.
  await app.listen(Number(process.env.API_PORT ?? 3001), process.env.API_HOST ?? '127.0.0.1');
}
void bootstrap();
