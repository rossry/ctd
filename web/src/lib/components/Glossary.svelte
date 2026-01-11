<script lang="ts">
	import { ChevronDown } from 'lucide-svelte';

	let expanded = $state(false);

	const glossaryTerms = [
		{ term: 'CSR', full: 'Clinical Study Report', description: 'Comprehensive document describing the methods, results, and analysis of a clinical trial.' },
		{ term: 'TLF', full: 'Tables, Listings, and Figures', description: 'Statistical outputs summarizing clinical trial data in tabular and graphical formats.' },
		{ term: 'ADaM', full: 'Analysis Data Model', description: 'CDISC standard for organizing analysis-ready datasets derived from clinical trial data.' },
		{ term: 'SDTM', full: 'Study Data Tabulation Model', description: 'CDISC standard for organizing raw clinical trial data in a consistent format.' },
		{ term: 'IND', full: 'Investigational New Drug', description: 'FDA application required before a new drug can be tested in humans.' },
		{ term: 'CRF', full: 'Case Report Form', description: 'Document used to collect data on each study participant during a clinical trial.' },
		{ term: 'IRB', full: 'Institutional Review Board', description: 'Committee that reviews and approves research involving human subjects.' },
		{ term: 'DSMB', full: 'Data Safety Monitoring Board', description: 'Independent group that monitors patient safety and study data during a trial.' },
		{ term: 'SAE', full: 'Serious Adverse Event', description: 'Medical event that results in death, hospitalization, disability, or is life-threatening.' },
		{ term: 'AE', full: 'Adverse Event', description: 'Any undesirable medical occurrence in a patient during a clinical trial.' },
		{ term: 'PK', full: 'Pharmacokinetics', description: 'Study of how the body absorbs, distributes, metabolizes, and excretes a drug.' },
		{ term: 'PD', full: 'Pharmacodynamics', description: 'Study of the biochemical and physiological effects of a drug on the body.' },
		{ term: 'CMC', full: 'Chemistry, Manufacturing, and Controls', description: 'Documentation of drug substance and product manufacturing processes and quality.' },
		{ term: 'TMF', full: 'Trial Master File', description: 'Collection of essential documents for a clinical trial that demonstrate compliance.' },
		{ term: 'ICF', full: 'Informed Consent Form', description: 'Document signed by participants confirming they understand and agree to the study.' },
		{ term: 'FDA', full: 'Food and Drug Administration', description: 'U.S. agency responsible for regulating drugs, biologics, and medical devices.' },
		{ term: 'CKD', full: 'Chronic Kidney Disease', description: 'Long-term condition where the kidneys do not work as well as they should.' },
		{ term: 'SAD', full: 'Single Ascending Dose', description: 'Phase 1 study design where single increasing doses are given to assess safety.' },
		{ term: 'MAD', full: 'Multiple Ascending Dose', description: 'Phase 1 study design where multiple increasing doses are given over time.' },
	];
</script>

<div class="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
	<button
		onclick={() => expanded = !expanded}
		class="w-full flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-800/50 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors text-left"
	>
		<div>
			<h3 class="font-medium text-gray-900 dark:text-gray-100">Glossary of Terms</h3>
			<p class="text-sm text-gray-500 dark:text-gray-400">Common regulatory and clinical trial abbreviations</p>
		</div>
		<ChevronDown class="h-5 w-5 text-gray-400 transition-transform duration-200 {expanded ? 'rotate-180' : ''}" />
	</button>

	{#if expanded}
		<div class="p-4 border-t border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
			<div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
				{#each glossaryTerms as { term, full, description }}
					<div class="text-sm">
						<div class="flex items-baseline gap-2">
							<span class="font-mono font-semibold text-blue-600 dark:text-blue-400">{term}</span>
							<span class="text-gray-700 dark:text-gray-300">{full}</span>
						</div>
						<p class="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{description}</p>
					</div>
				{/each}
			</div>
		</div>
	{/if}
</div>
