<?php

namespace App\Http\Controllers;

use App\Actions\CreateDatasetAction;
use App\Actions\DeleteDatasetAction;
use App\Actions\UpdateDatasetAction;
use App\Http\Requests\CreateDatasetRequest;
use App\Http\Requests\DeleteDatasetRequest;
use App\Http\Requests\UpdateDatasetRequest;
use App\Models\Dataset;
use App\Models\Organisation;
use App\Queries\GetOrganisationDatasetsQuery;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Inertia\Inertia;
use Inertia\Response;

class DatasetController extends Controller
{
    /**
     * Display a listing of the resource.
     */
    public function index(Request $request, Organisation $organisation, GetOrganisationDatasetsQuery $query): Response
    {
        $user = $request->user();

        // Ensure user belongs to this organisation
        if (! $user->organisations()->where('organisations.id', $organisation->id)->exists()) {
            abort(403);
        }

        $datasets = $query->execute($organisation)->get();

        $isAdmin = $user->isAdminOf($organisation);

        return Inertia::render('organisations/datasets/index', [
            'organisation' => $organisation,
            'datasets' => $datasets,
            'isAdmin' => $isAdmin,
        ]);
    }

    /**
     * Show the form for creating a new resource.
     */
    public function create(Request $request, Organisation $organisation): Response
    {
        $user = $request->user();

        // Ensure user belongs to this organisation
        if (! $user->organisations()->where('organisations.id', $organisation->id)->exists()) {
            abort(403);
        }

        // Only admins can create datasets
        if (! $user->isAdminOf($organisation)) {
            abort(403);
        }

        $dataset = new Dataset;

        return Inertia::render('organisations/datasets/create', [
            'organisation' => $organisation,
            'dataset' => $dataset,
        ]);
    }

    /**
     * Store a newly created resource in storage.
     */
    public function store(CreateDatasetRequest $request, Organisation $organisation, CreateDatasetAction $action): RedirectResponse
    {
        $dataset = $action->execute(
            $request->validated(),
            $organisation,
            $request->user()
        );

        return redirect()
            ->route('organisations.datasets.show', [$organisation, $dataset])
            ->with('success', 'Dataset created successfully.');
    }

    /**
     * Display the specified resource.
     */
    public function show(Request $request, Organisation $organisation, Dataset $dataset): Response
    {
        $user = $request->user();

        // Ensure user belongs to this organisation
        if (! $user->organisations()->where('organisations.id', $organisation->id)->exists()) {
            abort(403);
        }

        // Ensure dataset belongs to this organisation
        if ($dataset->organisation_id !== $organisation->id) {
            abort(404);
        }

        $dataset->loadCount(['files', 'conversations'])->load('owner');

        $isAdmin = $user->isAdminOf($organisation);

        return Inertia::render('organisations/datasets/show', [
            'organisation' => $organisation,
            'dataset' => $dataset,
            'isAdmin' => $isAdmin,
        ]);
    }

    /**
     * Show the form for editing the specified resource.
     */
    public function edit(Request $request, Organisation $organisation, Dataset $dataset): Response
    {
        $user = $request->user();

        // Ensure user belongs to this organisation
        if (! $user->organisations()->where('organisations.id', $organisation->id)->exists()) {
            abort(403);
        }

        // Ensure dataset belongs to this organisation
        if ($dataset->organisation_id !== $organisation->id) {
            abort(404);
        }

        // Only admins can edit datasets
        if (! $user->isAdminOf($organisation)) {
            abort(403);
        }

        return Inertia::render('organisations/datasets/edit', [
            'organisation' => $organisation,
            'dataset' => $dataset,
        ]);
    }

    /**
     * Update the specified resource in storage.
     */
    public function update(UpdateDatasetRequest $request, Organisation $organisation, Dataset $dataset, UpdateDatasetAction $action): RedirectResponse
    {
        // Ensure dataset belongs to this organisation
        if ($dataset->organisation_id !== $organisation->id) {
            abort(404);
        }

        $action->execute($request->validated(), $dataset);

        return redirect()
            ->route('organisations.datasets.show', [$organisation, $dataset])
            ->with('success', 'Dataset updated successfully.');
    }

    /**
     * Remove the specified resource from storage.
     */
    public function destroy(
        DeleteDatasetRequest $request,
        Organisation $organisation,
        Dataset $dataset,
        DeleteDatasetAction $action
    ): RedirectResponse {
        // Ensure dataset belongs to this organisation
        if ($dataset->organisation_id !== $organisation->id) {
            abort(404);
        }

        $action->execute(
            $dataset,
            $request->boolean('delete_files'),
            $request->boolean('delete_conversations')
        );

        return redirect()
            ->route('organisations.datasets.index', [$organisation])
            ->with('success', 'Dataset deleted successfully.');
    }
}
