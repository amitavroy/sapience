<?php

namespace App\Http\Controllers;

use App\Http\Requests\StartAuditRequest;
use App\Jobs\UrlSeoAudit;
use App\Models\Audit;
use App\Models\Organisation;
use Illuminate\Http\RedirectResponse;

class StartAuditController extends Controller
{
    /**
     * Handle the incoming request.
     */
    public function __invoke(StartAuditRequest $request, Organisation $organisation, Audit $audit): RedirectResponse
    {
        logger('Starting audit', [
            'audit_id' => $audit->id,
            'queue_connection' => config('queue.default'),
        ]);

        try {
            $job = UrlSeoAudit::dispatch($audit->website_url, $audit->id);
            logger('Job dispatched', [
                'audit_id' => $audit->id,
                'queue_connection' => config('queue.default'),
            ]);
        } catch (\Exception $e) {
            logger()->error('Failed to dispatch audit job', [
                'error' => $e->getMessage(),
                'trace' => $e->getTraceAsString(),
            ]);

            return redirect()
                ->route('organisations.audits.show', [$organisation, $audit])
                ->with('error', 'Failed to start audit. Please try again.');
        }

        return redirect()
            ->route('organisations.audits.show', [$organisation, $audit])
            ->with('success', 'Audit started successfully.');
    }
}
