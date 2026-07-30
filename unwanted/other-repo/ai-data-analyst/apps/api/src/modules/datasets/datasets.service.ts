import { Injectable } from '@nestjs/common';
import { parse } from 'csv-parse/sync';
import { Client } from 'pg';
import { PrismaService } from 'src/db/prisma.service';

@Injectable()
export class DatasetsService {
  constructor(private prisma: PrismaService) { }

  async handleUpload(body: { name: string }, file: { buffer: Buffer }) {
    // 1. Parse CSV
    const csvText = file.buffer.toString('utf8');
    const records = parse(csvText, { columns: true, skip_empty_lines: true });

    const columns = Object.keys(records[0]);

    // 2. Create metadata in Prisma
    const dataset = await this.prisma.dataset.create({
      data: { name: body.name, userId: 'TEMP-USER' },
    });

    const table = await this.prisma.datasetTable.create({
      data: {
        name: `dataset_${dataset.id.replace(/-/g, '')}`,
        datasetId: dataset.id,
        rowCount: records.length,
      },
    });

    // 3. Connect to Neon via pg client
    const client = new Client({ connectionString: process.env.DATABASE_URL });
    await client.connect();

    // 4. Dynamically create table in Postgres
    const createTableSQL = `
      CREATE TABLE "${table.name}" (
        id SERIAL PRIMARY KEY,
        ${columns.map((col) => `"${col}" TEXT`).join(',')}
      );
    `;
    await client.query(createTableSQL);

    // 5. Insert rows efficiently
    for (const row of records) {
      const values = columns.map((col) => (row as any)[col] ?? null);
      const placeholders = values.map((_, i) => `$${i + 1}`).join(',');

      await client.query(
        `INSERT INTO "${table.name}" (${columns.map((c) => `"${c}"`).join(',')})
         VALUES (${placeholders})`,
        values,
      );
    }

    await client.end();

    // 6. Save column metadata
    await this.prisma.datasetColumn.createMany({
      data: columns.map((col) => ({
        name: col,
        dataType: 'TEXT',
        isNullable: true,
        datasetId: dataset.id,
        tableId: table.id,
      })),
    });

    return {
      datasetId: dataset.id,
      rowsInserted: records.length,
      columns,
    };
  }
}
