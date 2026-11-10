import { Module } from '@nestjs/common';
import { AuthModule } from '../auth/auth.module';
import { BusinessModule } from '../business/business.module';
import { PagesController } from './pages.controller';
import { PagesService } from './pages.service';

@Module({ imports: [BusinessModule, AuthModule], controllers: [PagesController], providers: [PagesService] })
export class PagesModule {}
