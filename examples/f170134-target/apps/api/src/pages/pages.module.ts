import { Module } from '@nestjs/common';
import { BusinessModule } from '../business/business.module';
import { PagesController } from './pages.controller';
import { PagesService } from './pages.service';

@Module({ imports: [BusinessModule], controllers: [PagesController], providers: [PagesService] })
export class PagesModule {}
