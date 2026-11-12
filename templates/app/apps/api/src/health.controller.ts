import { Controller, Get } from '@nestjs/common';
import { DatabaseHealthService, Public } from '@apex2next/runtime-api';

@Controller()
export class HealthController {
  constructor(private readonly databaseHealth: DatabaseHealthService) {}

  @Public()
  @Get('health')
  health() {
    return { status: 'ok', service: '__APP_SLUG__-api' };
  }

  @Public()
  @Get('health/ready')
  readiness() {
    return this.databaseHealth.readiness();
  }
}
