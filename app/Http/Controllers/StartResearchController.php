<?php

namespace App\Http\Controllers;

use App\Http\Requests\StartResearchRequest;
use App\Jobs\ResearchProcessJob;
use App\Models\Organisation;
use App\Models\Research;
use Illuminate\Http\RedirectResponse;

class StartResearchController extends Controller
{
    /**
     * Handle the incoming request.
     */
    public function __invoke(StartResearchRequest $request, Organisation $organisation, Research $research): RedirectResponse
    {
        logger('Starting research', [
            'research_id' => $research->id,
            'queue_connection' => config('queue.default'),
        ]);

        try {
            $job = ResearchProcessJob::dispatch($research->id);
            logger('Job dispatched', [
                'research_id' => $research->id,
                'queue_connection' => config('queue.default'),
            ]);
        } catch (\Exception $e) {
            logger()->error('Failed to dispatch research job', [
                'error' => $e->getMessage(),
                'trace' => $e->getTraceAsString(),
            ]);

            return redirect()
                ->route('organisations.research.show', [$organisation, $research])
                ->with('error', 'Failed to start research. Please try again.');
        }

        return redirect()
            ->route('organisations.research.show', [$organisation, $research])
            ->with('success', 'Research started successfully.');
    }
}
