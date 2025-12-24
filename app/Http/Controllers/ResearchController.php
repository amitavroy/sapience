<?php

namespace App\Http\Controllers;

use App\Actions\CreateResearchAction;
use App\Actions\DeleteResearchAction;
use App\Actions\UpdateResearchAction;
use App\Http\Requests\CreateResearchRequest;
use App\Http\Requests\DeleteResearchRequest;
use App\Http\Requests\UpdateResearchRequest;
use App\Models\Organisation;
use App\Models\Research;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Inertia\Inertia;
use Inertia\Response;

class ResearchController extends Controller
{
    /**
     * Display a listing of researches for an organisation.
     */
    public function index(Request $request, Organisation $organisation): Response
    {
        $user = $request->user();

        // Ensure user belongs to this organisation
        if (! $user->organisations()->where('organisations.id', $organisation->id)->exists()) {
            abort(403);
        }

        $researches = Research::query()
            ->where('organisation_id', $organisation->id)
            ->with(['user', 'organisation'])
            ->orderBy('created_at', 'desc')
            ->paginate(15);

        return Inertia::render('organisations/research/index', [
            'organisation' => $organisation,
            'researches' => $researches,
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

        $research = new Research;

        return Inertia::render('organisations/research/create', [
            'organisation' => $organisation,
            'research' => $research,
        ]);
    }

    /**
     * Store a newly created resource in storage.
     */
    public function store(CreateResearchRequest $request, Organisation $organisation, CreateResearchAction $action): RedirectResponse
    {
        $research = $action->execute(
            $request->validated(),
            $organisation,
            $request->user()
        );

        return redirect()
            ->route('organisations.research.show', [$organisation, $research])
            ->with('success', 'Research created successfully.');
    }

    /**
     * Display the specified resource.
     */
    public function show(Request $request, Organisation $organisation, Research $research): Response
    {
        $user = $request->user();

        // Ensure user belongs to this organisation
        if (! $user->organisations()->where('organisations.id', $organisation->id)->exists()) {
            abort(403);
        }

        // Ensure research belongs to this organisation
        if ($research->organisation_id !== $organisation->id) {
            abort(404);
        }

        $research->load(['user', 'organisation']);

        $isOwner = $research->user_id === $user->id;

        return Inertia::render('organisations/research/show', [
            'organisation' => $organisation,
            'research' => $research,
            'isOwner' => $isOwner,
        ]);
    }

    /**
     * Show the form for editing the specified resource.
     */
    public function edit(Request $request, Organisation $organisation, Research $research): Response
    {
        $user = $request->user();

        // Ensure user belongs to this organisation
        if (! $user->organisations()->where('organisations.id', $organisation->id)->exists()) {
            abort(403);
        }

        // Ensure research belongs to this organisation
        if ($research->organisation_id !== $organisation->id) {
            abort(404);
        }

        // Only owner can edit research
        if ($research->user_id !== $user->id) {
            abort(403);
        }

        return Inertia::render('organisations/research/edit', [
            'organisation' => $organisation,
            'research' => $research,
        ]);
    }

    /**
     * Update the specified resource in storage.
     */
    public function update(UpdateResearchRequest $request, Organisation $organisation, Research $research, UpdateResearchAction $action): RedirectResponse
    {
        // Ensure research belongs to the organisation
        if ($research->organisation_id !== $organisation->id) {
            abort(404);
        }

        $action->execute($request->validated(), $research);

        return redirect()
            ->route('organisations.research.show', [$organisation, $research])
            ->with('success', 'Research updated successfully.');
    }

    /**
     * Remove the specified resource from storage.
     */
    public function destroy(
        DeleteResearchRequest $request,
        Organisation $organisation,
        Research $research,
        DeleteResearchAction $action
    ): RedirectResponse {
        // Ensure research belongs to the organisation
        if ($research->organisation_id !== $organisation->id) {
            abort(404);
        }

        $action->execute($research);

        return redirect()
            ->route('organisations.research.index', [$organisation])
            ->with('success', 'Research deleted successfully.');
    }
}
