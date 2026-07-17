import { Module } from '@nestjs/common';
import { AppController } from './app.controller';
import { AppService } from './app.service';
import { ConfigModule } from '@nestjs/config/dist/config.module';
import { DatasetsModule } from './modules/datasets/datasets.module';
import { TablesModule } from './modules/tables/tables.module';
import { ColumnsModule } from './modules/columns/columns.module';
import { QueriesModule } from './modules/queries/queries.module';
import { DashboardsModule } from './modules/dashboards/dashboards.module';
import { ChartsModule } from './modules/charts/charts.module';
import { AutomationsModule } from './modules/automations/automations.module';
import { AgentModule } from './modules/agent/agent.module';
import { McpModule } from './modules/mcp/mcp.module';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true, // make config available everywhere
      envFilePath: '.env',
    }),
    DatasetsModule,
    TablesModule,
    ColumnsModule,
    QueriesModule,
    DashboardsModule,
    ChartsModule,
    AutomationsModule,
    AgentModule,
    McpModule,
  ],
  controllers: [AppController],
  providers: [AppService],
})
export class AppModule {}
