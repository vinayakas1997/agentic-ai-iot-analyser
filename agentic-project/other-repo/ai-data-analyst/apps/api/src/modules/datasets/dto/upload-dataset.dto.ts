import { IsString } from 'class-validator';

export class UploadDatasetDto {
  @IsString()
  name: string;
}
