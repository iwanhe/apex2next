import {
  ArgumentMetadata,
  BadRequestException,
  Injectable,
  PipeTransform,
} from '@nestjs/common';
import {
  validateRuntimeItems,
  type RuntimeItem,
  type RuntimeValidationResult,
} from '@apex2next/shared-runtime';

/** Applies shared APEX-compatible item validation at a NestJS request boundary. */
@Injectable()
export class RuntimePageItemsPipe implements PipeTransform {
  constructor(private readonly items: readonly RuntimeItem[]) {}

  transform(value: unknown, _metadata: ArgumentMetadata): Readonly<Record<string, string | null>> {
    if (!value || typeof value !== 'object' || Array.isArray(value)) {
      throw new BadRequestException({
        code: 'INVALID_INPUT',
        message: 'Page item payload must be an object.',
      });
    }
    const result: RuntimeValidationResult = validateRuntimeItems(
      this.items,
      value as Readonly<Record<string, unknown>>,
    );
    if (result.errors.length) {
      throw new BadRequestException({
        code: 'VALIDATION_FAILED',
        message: 'One or more page items are invalid.',
        fieldErrors: result.errors,
      });
    }
    return result.values;
  }
}
