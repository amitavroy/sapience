<?php

$providers = [
    App\Providers\AppServiceProvider::class,
    App\Providers\FortifyServiceProvider::class,
    App\Providers\TelescopeServiceProvider::class,
];

if (config('sapience.oneuptime_tracing')) {
    $providers[] = App\Providers\OpenTelemetryServiceProvider::class;
}

return $providers;
