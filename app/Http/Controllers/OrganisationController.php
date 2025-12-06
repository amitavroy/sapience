<?php

namespace App\Http\Controllers;

use App\Http\Requests\CreateOrganisationRequest;
use App\Http\Requests\JoinOrganisationRequest;
use App\Http\Requests\SelectOrganisationRequest;
use App\Models\Organisation;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Inertia\Inertia;
use Inertia\Response;

class OrganisationController extends Controller
{
    /**
     * Show the organisation setup choice screen.
     */
    public function setup(): Response
    {
        return Inertia::render('organisations/setup');
    }

    /**
     * Show the organisation selection screen.
     */
    public function showSelect(Request $request): Response|RedirectResponse
    {
        $user = $request->user();
        $organisations = $user->organisations()->get();

        // If user has no organisations, redirect to setup
        if ($organisations->isEmpty()) {
            return redirect()->route('organisations.setup');
        }

        // If user has only one organisation, redirect to dashboard
        if ($organisations->count() === 1) {
            $organisation = $organisations->first();
            $user->update(['last_organisation_id' => $organisation->id]);

            return redirect()->route('organisations.dashboard', $organisation);
        }

        return Inertia::render('organisations/select', [
            'organisations' => $organisations,
        ]);
    }

    /**
     * Handle organisation selection.
     */
    public function select(SelectOrganisationRequest $request): RedirectResponse
    {
        $user = $request->user();
        $organisationId = $request->validated()['organisation_id'];
        $organisation = Organisation::findOrFail($organisationId);

        // Ensure user belongs to this organisation (validation already checks this)
        $user->update(['last_organisation_id' => $organisation->id]);

        return redirect()->route('organisations.dashboard', $organisation);
    }

    /**
     * Show the form to join an organisation.
     */
    public function showJoinForm(): Response
    {
        return Inertia::render('organisations/join');
    }

    /**
     * Handle joining an organisation by code.
     */
    public function join(JoinOrganisationRequest $request): RedirectResponse
    {
        $organisation = Organisation::query()
            ->where('uuid', $request->validated()['code'])
            ->firstOrFail();

        $user = $request->user();

        // Check if user is already a member
        if ($user->organisations()->where('organisations.id', $organisation->id)->exists()) {
            return redirect()->route('organisations.dashboard', $organisation);
        }

        $user->organisations()->attach($organisation->id, ['role' => 'member']);

        return redirect()
            ->route('organisations.dashboard', $organisation);
    }

    /**
     * Show the form to create a new organisation.
     */
    public function showCreateForm(): Response
    {
        return Inertia::render('organisations/create');
    }

    /**
     * Handle creating a new organisation.
     */
    public function store(CreateOrganisationRequest $request): RedirectResponse
    {
        $organisation = Organisation::create($request->validated());

        $request->user()
            ->organisations()
            ->attach($organisation->id, ['role' => 'admin']);

        return redirect()->route('organisations.dashboard', $organisation);
    }

    /**
     * Show the organisation dashboard.
     */
    public function dashboard(Request $request, Organisation $organisation): Response
    {
        $user = $request->user();

        // Ensure user belongs to this organisation
        if (! $user->organisations()->where('organisations.id', $organisation->id)->exists()) {
            abort(403);
        }

        // Update last_organisation_id when accessing dashboard
        if ($user->last_organisation_id !== $organisation->id) {
            $user->update(['last_organisation_id' => $organisation->id]);
        }

        return Inertia::render('organisations/dashboard', [
            'organisation' => $organisation->load('users'),
        ]);
    }
}
