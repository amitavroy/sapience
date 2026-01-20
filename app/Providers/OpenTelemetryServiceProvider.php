<?php

namespace App\Providers;

use Illuminate\Log\LogManager;
use Illuminate\Support\ServiceProvider;
use OpenTelemetry\API\Globals;
use OpenTelemetry\Contrib\Logs\Monolog\Handler;
use Psr\Log\LogLevel;
use Monolog\Logger;

class OpenTelemetryServiceProvider extends ServiceProvider
{
    public function register(): void
    {
        //
    }

    public function boot(): void
    {
        if (config('sapience.otel_php_autoload_enabled') && config('sapience.otel_logs_exporter') === 'otlp') {
            $this->setupOpenTelemetryLogging();
        }
    }

    private function setupOpenTelemetryLogging(): void
    {
        try {
            $loggerProvider = Globals::loggerProvider();
            $handler = new Handler($loggerProvider, LogLevel::INFO);

            // Get the default logger and add the OpenTelemetry handler
            $logger = app(LogManager::class)->driver();
            if (method_exists($logger, 'getLogger')) {
                $logger->getLogger()->pushHandler($handler);
            }
        } catch (\Exception $e) {
            // Silently fail if OpenTelemetry is not properly configured
            error_log('OpenTelemetry logging setup failed: ' . $e->getMessage());
        }
    }
}
