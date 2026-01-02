<?php

namespace App\Http\Controllers;

use App\Actions\Audit\CreateAuditAction;
use App\Actions\Audit\DeleteAuditAction;
use App\Http\Requests\CreateAuditRequest;
use App\Http\Requests\DeleteAuditRequest;
use App\Models\Audit;
use App\Models\Organisation;
use Illuminate\Http\JsonResponse;
use Illuminate\Http\RedirectResponse;
use Illuminate\Http\Request;
use Inertia\Inertia;
use Inertia\Response;

class AuditController extends Controller
{
    /**
     * Display a listing of audits for an organisation.
     */
    public function index(Request $request, Organisation $organisation): Response|JsonResponse
    {
        $user = $request->user();

        // Ensure user belongs to this organisation
        if (! $user->organisations()->where('organisations.id', $organisation->id)->exists()) {
            abort(403);
        }

        $perPage = $request->input('per_page', 15);
        $search = $request->input('search');

        $query = Audit::query()
            ->where('organisation_id', $organisation->id)
            ->with(['user', 'organisation'])
            ->orderBy('created_at', 'desc');

        if ($search) {
            $query->where('website_url', 'like', "%{$search}%");
        }

        $audits = $query->paginate($perPage);

        // Return JSON if requested via AJAX
        if ($request->wantsJson()) {
            return response()->json($audits);
        }

        return Inertia::render('organisations/audits/index', [
            'organisation' => $organisation,
            'audits' => $audits,
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

        $audit = new Audit;

        return Inertia::render('organisations/audits/create', [
            'organisation' => $organisation,
            'audit' => $audit,
        ]);
    }

    /**
     * Store a newly created resource in storage.
     */
    public function store(CreateAuditRequest $request, Organisation $organisation, CreateAuditAction $action): RedirectResponse
    {
        $audit = $action->execute(
            $request->validated(),
            $organisation,
            $request->user()
        );

        return redirect()
            ->route('organisations.audits.show', [$organisation, $audit])
            ->with('success', 'Audit created successfully.');
    }

    /**
     * Display the specified resource.
     */
    public function show(Request $request, Organisation $organisation, Audit $audit): Response
    {
        $user = $request->user();

        // Ensure user belongs to this organisation
        if (! $user->organisations()->where('organisations.id', $organisation->id)->exists()) {
            abort(403);
        }

        // Ensure audit belongs to this organisation
        if ($audit->organisation_id !== $organisation->id) {
            abort(404);
        }

        $audit->load(['user', 'organisation', 'auditLinks']);

        $isOwner = $audit->user_id === $user->id;

        return Inertia::render('organisations/audits/show', [
            'organisation' => $organisation,
            'audit' => $audit,
            'isOwner' => $isOwner,
        ]);
    }

    /**
     * Remove the specified resource from storage.
     */
    public function destroy(
        DeleteAuditRequest $request,
        Organisation $organisation,
        Audit $audit,
        DeleteAuditAction $action
    ): RedirectResponse {
        // Ensure audit belongs to the organisation
        if ($audit->organisation_id !== $organisation->id) {
            abort(404);
        }

        $action->execute($audit);

        return redirect()
            ->route('organisations.audits.index', [$organisation])
            ->with('success', 'Audit deleted successfully.');
    }
}
