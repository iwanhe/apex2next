import { Controller, Get } from '@nestjs/common';
import { Public } from './auth/auth.guard';
import { DatabaseHealthService } from './database/database-health.service';

@Controller()
export class HealthController {
  constructor(private readonly databaseHealth: DatabaseHealthService) {}

  @Public()
  @Get('health')
  health() {
    return { status: 'ok', service: 'apex2next-f170134-api' };
  }

  @Public()
  @Get('health/ready')
  readiness() {
    return this.databaseHealth.readiness();
  }
}
