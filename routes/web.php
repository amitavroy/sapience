<?php

use App\Http\Controllers\DatasetController;
use App\Http\Controllers\FileController;
use App\Http\Controllers\OrganisationController;
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
    });
});

require __DIR__.'/settings.php';

Route::get('chat', function () {
    // Requires organisationId and datasetId
    $response = (new SapienceBot(
        organisationId: 1,
        datasetId: 2,
    ))->chat(new UserMessage('When did I go to Hampi?'));

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
