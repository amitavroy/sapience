<?php

use Inertia\Inertia;
use Laravel\Fortify\Features;
use OpenTelemetry\API\Globals;
use Illuminate\Support\Facades\Route;
use App\Http\Controllers\FileController;
use App\Http\Controllers\AuditController;
use App\Http\Controllers\DatasetController;
use App\Http\Controllers\ResearchController;
use App\Http\Controllers\StartAuditController;
use App\Http\Controllers\ConversationController;
use App\Http\Controllers\OrganisationController;
use App\Http\Controllers\StartResearchController;
use App\Http\Middleware\EnsureUserHasOrganisation;

Route::get('/', function () {
    return Inertia::render('welcome', [
        'canRegister' => Features::enabled(Features::registration()),
    ]);
})->name('home');

Route::middleware(['auth', 'verified'])->group(function () {
    Route::get('dashboard', function () {
        return Inertia::render('dashboard');
    })->middleware(EnsureUserHasOrganisation::class)->name('dashboard');

    Route::prefix('organisations')->name('organisations.')->group(function () {
        Route::get('setup', [OrganisationController::class, 'setup'])->name('setup');
        Route::get('select', [OrganisationController::class, 'showSelect'])->name('select');
        Route::post('select', [OrganisationController::class, 'select'])->name('select.store');
        Route::get('join', [OrganisationController::class, 'showJoinForm'])->name('join');
        Route::post('join', [OrganisationController::class, 'join'])->name('join.store');
        Route::get('create', [OrganisationController::class, 'showCreateForm'])->name('create');
        Route::post('/', [OrganisationController::class, 'store'])->name('store');

        Route::get('{organisation}/dashboard', [OrganisationController::class, 'dashboard'])->name('dashboard');

        Route::prefix('{organisation}/conversations')->name('conversations.')->group(function () {
            Route::get('/', [ConversationController::class, 'index'])->name('index');
            Route::delete('{conversation}', [ConversationController::class, 'destroy'])->name('destroy');
        });

        Route::resource('{organisation}/datasets', DatasetController::class)
            ->names([
                'index' => 'datasets.index',
                'create' => 'datasets.create',
                'store' => 'datasets.store',
                'show' => 'datasets.show',
                'edit' => 'datasets.edit',
                'update' => 'datasets.update',
            ]);

        Route::prefix('{organisation}/datasets/{dataset}/files')->name('datasets.files.')->group(function () {
            Route::post('request-upload', [FileController::class, 'requestUpload'])->name('request-upload');
            Route::post('complete', [FileController::class, 'completeUpload'])->name('complete');
            Route::get('/', [FileController::class, 'index'])->name('index');
            Route::delete('{file}', [FileController::class, 'destroy'])->name('destroy');
        });

        Route::prefix('{organisation}/datasets/{dataset}/conversations')->name('datasets.conversations.')->group(function () {
            Route::post('/', [ConversationController::class, 'store'])->name('store');
            Route::get('{conversation}', [ConversationController::class, 'show'])->name('show');
        });

        Route::resource('{organisation}/research', ResearchController::class)
            ->names([
                'index' => 'research.index',
                'create' => 'research.create',
                'store' => 'research.store',
                'show' => 'research.show',
                'edit' => 'research.edit',
                'update' => 'research.update',
                'destroy' => 'research.destroy',
            ]);

        Route::post('{organisation}/research/{research}/start', StartResearchController::class)
            ->name('research.start');

        Route::resource('{organisation}/audits', AuditController::class)
            ->names([
                'index' => 'audits.index',
                'create' => 'audits.create',
                'store' => 'audits.store',
                'show' => 'audits.show',
                'destroy' => 'audits.destroy',
            ]);

        Route::post('{organisation}/audits/{audit}/start', StartAuditController::class)
            ->name('audits.start');
    });

    Route::prefix('api/v1')->name('api.v1.')->group(function () {
        Route::post('conversations/{conversation}/messages', [ConversationController::class, 'sendMessage'])->name('conversations.messages.store');
    });
});

require __DIR__.'/settings.php';

Route::get('/test-logs', function () {
    logger()->info('Test info log', ['user_id' => 123]);
    logger()->error('Test error log', ['error_code' => 500]);
    logger()->warning('Test warning log');

    return response()->json([
        'status' => 'success',
        'message' => 'Logs generated - check OneUptime dashboard'
    ]);
});

Route::get('/apm-test', function () {
    $tracer = Globals::tracerProvider()->getTracer('laravel-demo-1234567890');

    $span = $tracer->spanBuilder('apm-test-operation')
        ->setAttribute('user.id', 123)
        ->setAttribute('operation.type', 'test')
        ->startSpan();

    sleep(1);

    logger()->info('APM test executed', ['operation' => 'apm-test']);

    $span->addEvent('operation completed', ['result' => 'success']);
    $span->end();

    return response()->json([
        'status' => 'success',
        'message' => 'APM trace generated',
        'timestamp' => now()
    ]);
});
