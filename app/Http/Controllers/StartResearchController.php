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
        $isResuming = $this->isResumingWorkflow($research);

        if ($isResuming) {
            $this->prepareResume($request, $research);
        }

        try {
            $this->dispatchResearchJob($research->id, $isResuming);
        } catch (\Exception $e) {
            return $this->handleDispatchError($e, $isResuming, $organisation, $research);
        }

        return $this->redirectWithSuccess($organisation, $research, $isResuming);
    }

    /**
     * Check if we're resuming an existing workflow
     */
    private function isResumingWorkflow(Research $research): bool
    {
        return $research->workflow_id && $research->status === 'awaiting_feedback';
    }

    /**
     * Prepare research for resume by storing user feedback
     */
    private function prepareResume(StartResearchRequest $request, Research $research): void
    {
        logger('Resuming research', [
            'research_id' => $research->id,
            'workflow_id' => $research->workflow_id,
            'queue_connection' => config('queue.default'),
        ]);

        $feedback = $this->extractFeedbackFromRequest($request);
        $this->storeFeedbackForResume($research, $feedback);
    }

    /**
     * Extract feedback data from request
     */
    private function extractFeedbackFromRequest(StartResearchRequest $request): array
    {
        $feedback = [];

        if ($request->filled('additional_context')) {
            $feedback['additional_context'] = $request->input('additional_context');
        }

        if ($request->filled('refined_search_terms')) {
            $feedback['refined_search_terms'] = $request->input('refined_search_terms');
        }

        return $feedback;
    }

    /**
     * Store feedback in research interruption_data for job to pick up
     */
    private function storeFeedbackForResume(Research $research, array $feedback): void
    {
        $interruptionData = $research->interruption_data ?? [];
        $interruptionData['user_feedback'] = $feedback;

        $research->update([
            'interruption_data' => $interruptionData,
            'status' => 'processing',
        ]);
    }

    /**
     * Dispatch research process job
     */
    private function dispatchResearchJob(int $researchId, bool $isResuming): void
    {
        ResearchProcessJob::dispatch($researchId);

        logger('Job dispatched', [
            'research_id' => $researchId,
            'is_resuming' => $isResuming,
            'queue_connection' => config('queue.default'),
        ]);
    }

    /**
     * Handle job dispatch errors
     */
    private function handleDispatchError(\Exception $e, bool $isResuming, Organisation $organisation, Research $research): RedirectResponse
    {
        logger()->error('Failed to dispatch research job', [
            'error' => $e->getMessage(),
            'trace' => $e->getTraceAsString(),
        ]);

        if ($isResuming) {
            $research->update(['status' => 'awaiting_feedback']);
        }

        return redirect()
            ->route('organisations.research.show', [$organisation, $research])
            ->with('error', 'Failed to start research. Please try again.');
    }

    /**
     * Redirect with success message
     */
    private function redirectWithSuccess(Organisation $organisation, Research $research, bool $isResuming): RedirectResponse
    {
        $message = $isResuming ? 'Research resumed successfully.' : 'Research started successfully.';

        return redirect()
            ->route('organisations.research.show', [$organisation, $research])
            ->with('success', $message);
    }
}
