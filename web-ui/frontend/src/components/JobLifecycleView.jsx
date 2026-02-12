import React, { useEffect, useState } from 'react';
import { supabase } from '../supabase';
import IntakeChatView from './IntakeChatView';
import PlanProposalView from './PlanProposalView';
import ReviewView from './ReviewView';

/**
 * JobLifecycleView: Main component that manages the job lifecycle UI.
 * 
 * Displays different views based on job status:
 * - INTAKE_CLARIFICATION → IntakeChatView
 * - PLAN_PROPOSED → PlanProposalView
 * - RUNNING → ProgressView
 * - JOB_READY → ReviewView
 * - COMPLETED → CompletionView
 */
export function JobLifecycleView({ jobId }) {
  const [job, setJob] = useState(null);
  const [clarifications, setClarifications] = useState([]);
  const [plan, setPlan] = useState(null);
  const [artifacts, setArtifacts] = useState([]);
  const [jobSteps, setJobSteps] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Subscribe to real-time updates
  useEffect(() => {
    if (!jobId) return;

    const loadJobData = async () => {
      try {
        // Load job
        const { data: jobData, error: jobError } = await supabase
          .from('jobs')
          .select('*')
          .eq('id', jobId)
          .single();

        if (jobError) throw jobError;
        setJob(jobData);

        // Load clarifications
        const { data: clarData, error: clarError } = await supabase
          .from('clarifications')
          .select('*')
          .eq('job_id', jobId)
          .order('asked_at', { ascending: false });

        if (!clarError && clarData) {
          setClarifications(clarData);
        }

        // Load job steps
        const { data: stepsData, error: stepsError } = await supabase
          .from('job_steps')
          .select('*')
          .eq('job_id', jobId)
          .order('step_index', { ascending: true });

        if (!stepsError && stepsData) {
          setJobSteps(stepsData);
        }

        // Load artifacts
        const { data: artData, error: artError } = await supabase
          .from('artifacts')
          .select('*')
          .eq('job_id', jobId)
          .order('created_at', { ascending: false });

        if (!artError && artData) {
          setArtifacts(artData);
        }

        setLoading(false);
      } catch (err) {
        setError(err.message);
        setLoading(false);
      }
    };

    loadJobData();

    // Subscribe to changes
    const jobSubscription = supabase
      .from('jobs')
      .on('*', payload => {
        if (payload.new.id === jobId) {
          setJob(payload.new);
        }
      })
      .subscribe();

    const clarSubscription = supabase
      .from('clarifications')
      .on('*', payload => {
        if (payload.new?.job_id === jobId) {
          setClarifications(prev => [...prev, payload.new].sort((a, b) => 
            new Date(b.asked_at) - new Date(a.asked_at)
          ));
        }
      })
      .subscribe();

    const stepsSubscription = supabase
      .from('job_steps')
      .on('*', payload => {
        if (payload.new?.job_id === jobId) {
          setJobSteps(prev => [...prev.filter(s => s.id !== payload.new.id), payload.new].sort((a, b) => a.step_index - b.step_index));
        }
      })
      .subscribe();

    const artSubscription = supabase
      .from('artifacts')
      .on('*', payload => {
        if (payload.new?.job_id === jobId) {
          setArtifacts(prev => [payload.new, ...prev.filter(a => a.id !== payload.new.id)]);
        }
      })
      .subscribe();

    return () => {
      jobSubscription.unsubscribe();
      clarSubscription.unsubscribe();
      stepsSubscription.unsubscribe();
      artSubscription.unsubscribe();
    };
  }, [jobId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading job details...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6 bg-red-50 border border-red-200 rounded text-red-800">
        <h3 className="font-semibold mb-2">Error Loading Job</h3>
        <p>{error}</p>
      </div>
    );
  }

  if (!job) {
    return <div className="p-6 text-gray-500">Job not found</div>;
  }

  // Extract plan from job context
  const extractedPlan = job.context?.plan;

  return (
    <div className="flex flex-col gap-6">
      {/* Status Badge */}
      <StatusBadge status={job.status} />

      {/* Life cycle view based on status */}
      {job.status === 'INTAKE_CLARIFICATION' && (
        <IntakeChatView
          jobId={jobId}
          clarifications={clarifications.filter(c => !c.user_answer)}
          onAnswersSubmitted={() => {
            // Refresh data
          }}
        />
      )}

      {job.status === 'PLAN_PROPOSED' && (
        <PlanProposalView
          jobId={jobId}
          plan={extractedPlan}
          onApprove={() => {
            // Plan approved
          }}
          onRequestChanges={() => {
            // Back to intake
          }}
        />
      )}

      {job.status === 'RUNNING' && (
        <ProgressView jobSteps={jobSteps} />
      )}

      {job.status === 'AWAITING_APPROVAL' && (
        <AwaitingApprovalView jobSteps={jobSteps} />
      )}

      {job.status === 'JOB_READY' && (
        <ReviewView
          jobId={jobId}
          artifacts={artifacts.filter(art => {
            const hasOriginal = art.original_data && Object.keys(art.original_data).length > 0;
            const hasProposed = art.proposed_data && Object.keys(art.proposed_data).length > 0;
            return (hasOriginal || hasProposed) && art.artifact_type !== 'context';
          })}
          ceoSummary={job.context?.ceo_summary}
          onApprove={() => {
            // Job completed
          }}
          onRequestChanges={() => {
            // Back to running
          }}
        />
      )}

      {job.status === 'COMPLETED' && (
        <CompletionView jobContext={job.context} />
      )}

      {job.status === 'FAILED' && (
        <FailureView errorMessage={job.context?.error} />
      )}
    </div>
  );
}

/**
 * Status badge showing current job status
 */
function StatusBadge({ status }) {
  const statusConfig = {
    INTAKE_CLARIFICATION: { color: 'bg-blue-100 text-blue-800', label: '💬 Clarifying...' },
    PLAN_PROPOSED: { color: 'bg-purple-100 text-purple-800', label: '📋 Plan Ready' },
    RUNNING: { color: 'bg-yellow-100 text-yellow-800', label: '⚙️ Working...' },
    AWAITING_APPROVAL: { color: 'bg-yellow-100 text-yellow-800', label: '⏸️ Awaiting Approval' },
    JOB_READY: { color: 'bg-orange-100 text-orange-800', label: '✍️ Ready for Review' },
    COMPLETED: { color: 'bg-green-100 text-green-800', label: '✅ Completed' },
    FAILED: { color: 'bg-red-100 text-red-800', label: '❌ Failed' }
  };

  const config = statusConfig[status] || { color: 'bg-gray-100 text-gray-800', label: status };

  return (
    <div className={`inline-block px-4 py-2 rounded-full font-semibold ${config.color}`}>
      {config.label}
    </div>
  );
}

/**
 * Progress view showing real-time execution progress
 */
function ProgressView({ jobSteps }) {
  return (
    <div className="p-6 bg-white rounded-lg border border-gray-200">
      <h2 className="text-2xl font-bold mb-4">⚙️ Execution in Progress</h2>
      
      <div className="space-y-4">
        {jobSteps.map((step, idx) => (
          <div
            key={step.id}
            className="flex items-start gap-4 p-4 border border-gray-200 rounded"
          >
            <div className="flex-shrink-0">
              {step.status === 'success' && (
                <div className="w-8 h-8 rounded-full bg-green-500 text-white flex items-center justify-center">
                  ✓
                </div>
              )}
              {step.status === 'in_progress' && (
                <div className="w-8 h-8 rounded-full bg-blue-500 text-white flex items-center justify-center animate-pulse">
                  ⚙
                </div>
              )}
              {step.status === 'pending' && (
                <div className="w-8 h-8 rounded-full bg-gray-300 text-white flex items-center justify-center">
                  •
                </div>
              )}
              {step.status === 'failed' && (
                <div className="w-8 h-8 rounded-full bg-red-500 text-white flex items-center justify-center">
                  ✕
                </div>
              )}
              {step.status === 'awaiting_approval' && (
                <div className="w-8 h-8 rounded-full bg-yellow-500 text-white flex items-center justify-center">
                  ⏸
                </div>
              )}
            </div>
            <div className="flex-grow">
              <p className="font-semibold text-gray-800">
                Step {step.step_index}: {step.agent_role}
              </p>
              {step.timing_ms > 0 && (
                <p className="text-xs text-gray-500 mt-1">
                  Completed in {(step.timing_ms / 1000).toFixed(1)}s
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Awaiting approval view
 */
function AwaitingApprovalView({ jobSteps }) {
  const latestPause = [...jobSteps]
    .reverse()
    .find(step => step.status === 'awaiting_approval');

  return (
    <div className="p-6 bg-yellow-50 border border-yellow-200 rounded-lg">
      <h2 className="text-2xl font-bold mb-2">⏸️ Awaiting Approval</h2>
      <p className="text-gray-700">
        An approval is required before we can continue. Review the details below.
      </p>
      {latestPause?.output?.reason && (
        <div className="mt-4 p-4 bg-white border border-yellow-200 rounded">
          <p className="text-sm font-semibold text-yellow-900 mb-2">Reason</p>
          <p className="text-sm text-gray-700">{latestPause.output.reason}</p>
        </div>
      )}
    </div>
  );
}

/**
 * Completion view showing final result
 */
function CompletionView({ jobContext }) {
  return (
    <div className="p-6 bg-green-50 border-2 border-green-200 rounded-lg text-center">
      <div className="text-5xl mb-4">✅</div>
      <h2 className="text-2xl font-bold text-green-900 mb-2">Job Completed!</h2>
      <p className="text-gray-700">
        Your job has been successfully approved and deployed.
      </p>
      {jobContext?.deployment_url && (
        <a
          href={jobContext.deployment_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-block mt-4 px-6 py-3 bg-green-600 text-white rounded font-semibold hover:bg-green-700"
        >
          View Live Result
        </a>
      )}
    </div>
  );
}

/**
 * Failure view showing error details
 */
function FailureView({ errorMessage }) {
  return (
    <div className="p-6 bg-red-50 border-2 border-red-200 rounded-lg">
      <h2 className="text-2xl font-bold text-red-900 mb-2">❌ Job Failed</h2>
      {errorMessage && (
        <p className="text-gray-700 mt-4 p-4 bg-red-100 rounded">
          {errorMessage}
        </p>
      )}
      <p className="text-sm text-gray-600 mt-4">
        Please contact support if this issue persists.
      </p>
    </div>
  );
}

export default JobLifecycleView;
