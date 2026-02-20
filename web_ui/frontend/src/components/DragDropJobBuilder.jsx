import { useState } from 'react'
import { DndContext, closestCenter } from '@dnd-kit/core'
import { SortableContext, useSortable, verticalListSortingStrategy, arrayMove } from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'

function SortableStep({ step }) {
  const { attributes, listeners, setNodeRef, transform, transition } = useSortable({ id: step.id })

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  }

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className="bg-white p-4 rounded-lg shadow cursor-move mb-2"
    >
      <div className="flex items-center gap-3">
        <svg className="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
        </svg>
        <span className="font-medium">{step.name}</span>
      </div>
    </div>
  )
}

export function DragDropJobBuilder() {
  const [steps, setSteps] = useState([
    { id: '1', name: 'Research' },
    { id: '2', name: 'Write' },
    { id: '3', name: 'Review' },
    { id: '4', name: 'Publish' },
  ])

  function handleDragEnd(event) {
    const { active, over } = event

    if (!over || active.id === over.id) return

    setSteps((items) => {
      const oldIndex = items.findIndex((i) => i.id === active.id)
      const newIndex = items.findIndex((i) => i.id === over.id)
      return arrayMove(items, oldIndex, newIndex)
    })
  }

  return (
    <div className="p-6 bg-gray-50 rounded-xl border border-gray-200">
      <h2 className="text-xl font-bold mb-1">Build Your Workflow</h2>
      <p className="text-sm text-gray-500 mb-4">Drag to reorder the default steps before you start.</p>
      <DndContext collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
        <SortableContext items={steps} strategy={verticalListSortingStrategy}>
          {steps.map((step) => (
            <SortableStep key={step.id} step={step} />
          ))}
        </SortableContext>
      </DndContext>
    </div>
  )
}
