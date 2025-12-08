<?php

use App\Http\Controllers\FileController;
use App\Http\Middleware\EnsureUserHasOrganisation;
use App\Neuron\SapienceBot;
use Illuminate\Support\Facades\Route;
use Inertia\Inertia;
use Laravel\Fortify\Features;
use NeuronAI\Chat\Messages\UserMessage;
use NeuronAI\RAG\DataLoader\FileDataLoader;

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
        Route::get('setup', [\App\Http\Controllers\OrganisationController::class, 'setup'])->name('setup');
        Route::get('select', [\App\Http\Controllers\OrganisationController::class, 'showSelect'])->name('select');
        Route::post('select', [\App\Http\Controllers\OrganisationController::class, 'select'])->name('select.store');
        Route::get('join', [\App\Http\Controllers\OrganisationController::class, 'showJoinForm'])->name('join');
        Route::post('join', [\App\Http\Controllers\OrganisationController::class, 'join'])->name('join.store');
        Route::get('create', [\App\Http\Controllers\OrganisationController::class, 'showCreateForm'])->name('create');
        Route::post('/', [\App\Http\Controllers\OrganisationController::class, 'store'])->name('store');
        Route::get('{organisation}/dashboard', [\App\Http\Controllers\OrganisationController::class, 'dashboard'])->name('dashboard');

        Route::resource('{organisation}/datasets', \App\Http\Controllers\DatasetController::class)
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
    });
});

require __DIR__.'/settings.php';

Route::get('chat', function () {
    $response = SapienceBot::make()
        ->chat(new UserMessage('Who is Amitav Roy?'));

    echo $response->getContent();
});

Route::get('test', function () {
    // SapienceBot::make()->addDocuments(
    //     FileDataLoader::for(storage_path('app/docs/todo.md'))
    //         ->getDocuments()
    // );
    // return FileDataLoader::for(storage_path('app/docs/todo.md'))
    //     ->getDocuments();
});
