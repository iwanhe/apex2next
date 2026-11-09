import { Controller, Get } from '@nestjs/common';
import { DatabaseHealthService } from './database/database-health.service';

@Controller()
export class HealthController {
  constructor(private readonly databaseHealth: DatabaseHealthService) {}

  @Get('health')
  health() {
    return { status: 'ok', service: 'apex2next-generated-api' };
  }

  @Get('health/ready')
  readiness() {
    return this.databaseHealth.readiness();
  }
}
