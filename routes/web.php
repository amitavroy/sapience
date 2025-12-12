<?php

use App\Http\Controllers\ConversationController;
use App\Http\Controllers\DatasetController;
use App\Http\Controllers\FileController;
use App\Http\Controllers\OrganisationController;
use App\Http\Middleware\EnsureUserHasOrganisation;
use Illuminate\Support\Facades\Route;
use Inertia\Inertia;
use Laravel\Fortify\Features;

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
    });

    Route::prefix('api/v1')->name('api.v1.')->group(function () {
        Route::post('conversations/{conversation}/messages', [ConversationController::class, 'sendMessage'])->name('conversations.messages.store');
    });
});

require __DIR__.'/settings.php';
