import { Controller, Post, Body, Req } from '@nestjs/common';
import { FastifyRequest } from 'fastify';
import { UploadDatasetDto } from './dto/upload-dataset.dto';
import { DatasetsService } from './datasets.service';

@Controller('datasets')
export class DatasetsController {
  constructor(private readonly datasetsService: DatasetsService) { }

  @Post('upload')
  async uploadDataset(
    @Body() body: UploadDatasetDto,
    @Req() req: FastifyRequest,
  ) {
    const file = await req.file();
    if (!file) {
      throw new Error('File is required');
    }
    const buffer = await file.toBuffer();
    return this.datasetsService.handleUpload(body, { buffer });
  }
}
