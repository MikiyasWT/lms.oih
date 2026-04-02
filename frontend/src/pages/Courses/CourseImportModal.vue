<template>
	<Dialog
		v-model="show"
		:options="{
			title: __('Import Course from ZIP'),
		}"
	>
		<template #body-content>
			<div class="text-p-base">
				<div
					v-if="!zip"
					@dragover.prevent
					@drop.prevent="(e) => uploadFile(e)"
					class="h-[100px] flex flex-col items-center justify-center bg-surface-gray-1 border border-dashed border-outline-gray-3 rounded-md"
				>
					<div v-if="!uploading" class="w-4/5 text-center">
						<UploadCloud
							class="size-6 stroke-1.5 text-ink-gray-6 mx-auto mb-2.5"
						/>
						<input
							ref="fileInput"
							type="file"
							accept=".zip"
							class="hidden"
							@change="(e) => uploadFile(e)"
						/>
						<div class="leading-5 text-ink-gray-9">
							{{ __('Drag and drop a ZIP file, or upload from your') }}
							<span
								@click="openFileSelector"
								class="cursor-pointer font-semibold hover:underline"
							>
								{{ __('Device') }}
							</span>
						</div>
					</div>
					<div
						v-else-if="uploading"
						class="w-4/5 lg:w-2/5 bg-surface-white border rounded-md p-2"
					>
						<div class="space-y-2">
							<div class="font-medium">
								{{ uploadingFile.name }}
							</div>
							<div class="text-ink-gray-6">
								{{ convertToMB(uploaded) }} of {{ convertToMB(total) }}
							</div>
						</div>
						<div class="w-full bg-surface-gray-1 h-1 rounded-full mt-3">
							<div
								class="bg-surface-gray-7 h-1 rounded-full transition-all duration-500 ease-in-out"
								:style="`width: ${uploadProgress}%`"
							></div>
						</div>
					</div>
				</div>
				<div
					v-else-if="zip"
					class="h-[100px] flex items-center justify-center bg-surface-gray-1 border border-dashed border-outline-gray-3 rounded-md"
				>
					<div
						class="w-4/5 lg:w-3/5 bg-surface-white border rounded-md p-2 flex items-center justify-between items-center"
					>
						<div class="space-y-2">
							<div class="font-medium leading-5 text-ink-gray-9">
								{{ zip.file_name || zip.name }}
							</div>
							<div v-if="zip.file_size" class="text-ink-gray-6">
								{{ convertToMB(zip.file_size) }}
							</div>
						</div>
						<Trash2
							class="size-4 stroke-1.5 text-ink-red-3 cursor-pointer"
							@click="deleteFile"
						/>
					</div>
				</div>
			</div>
		</template>
		<template #actions>
			<div class="flex justify-end">
				<Button variant="solid" @click="importZip">
					{{ __('Import') }}
				</Button>
			</div>
		</template>
	</Dialog>
</template>
<script setup lang="ts">
import { Button, call, Dialog, FileUploadHandler, toast } from 'frappe-ui'
import { computed, ref } from 'vue'
import { Trash, UploadCloud } from 'lucide-vue-next'
import { Trash2 } from 'lucide-vue-next'

const fileInput = ref<HTMLInputElement | null>(null)
const show = defineModel<boolean>({ required: true, default: false })
const zip = ref<any | null>(null)
const uploaded = ref(0)
const total = ref(0)
const uploading = ref(false)
const uploadingFile = ref<any | null>(null)

const openFileSelector = () => {
	fileInput.value?.click()
}

const uploadProgress = computed(() => {
	if (total.value === 0) return 0
	return Math.floor((uploaded.value / total.value) * 100)
})

const extractFile = (e: Event): File | null => {
	const inputFiles = (e.target as HTMLInputElement)?.files
	const dt = (e as DragEvent).dataTransfer?.files

	return inputFiles?.[0] || dt?.[0] || null
}

const validateFile = (file: File) => {
	const extension = file.name.split('.').pop()?.toLowerCase()
	if (extension !== 'zip') {
		toast.error('Please upload a valid ZIP file.')
		console.error('Please upload a valid ZIP file.')
	}
	return extension
}

const uploadFile = (e: Event) => {
	const file = extractFile(e)
	if (!file) return

	let fileType = validateFile(file)
	if (fileType !== 'zip') return

	uploadingFile.value = file
	const uploader = new FileUploadHandler()

	uploader.on('start', () => {
		uploading.value = true
	})

	uploader.on('progress', (data: { uploaded: number; total: number }) => {
		uploaded.value = data.uploaded
		total.value = data.total
		console.log(uploaded.value, total.value)
	})

	uploader.on('error', (error: any) => {
		uploading.value = false
		toast.error(error)
		console.error('File upload error:', error)
	})

	uploader.on('finish', () => {
		uploading.value = false
	})
	uploader
		.upload(file, {
			private: 0,
		})
		.then((data: any) => {
			zip.value = data
		})
		.catch((error: any) => {
			console.error('File upload error:', error)
		})
}

const importZip = () => {
	if (!zip.value) return
	call('lms.lms.api.import_course_as_zip', {
		zip_file_path: zip.value.file_url,
	})
		.then(() => {
			toast.success('Course imported successfully!')
			show.value = false
			deleteFile()
		})
		.catch((error: any) => {
			toast.error('Error importing course: ' + error.message)
			console.error('Error importing course:', error)
		})
}

const deleteFile = () => {
	zip.value = null
}

const convertToMB = (bytes: number) => {
	return (bytes / 1024 / 1024).toFixed(2) + ' MB'
}
</script>
