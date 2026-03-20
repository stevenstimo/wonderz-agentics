/**
 * PdfBase.jsx
 * Gedeelde stijlen en layout-primitives voor alle PDF exports in het platform.
 * Gebruik deze als basis voor elke nieuwe PDF, niet als standalone document.
 */
import { StyleSheet } from '@react-pdf/renderer'

export const pdfStyles = StyleSheet.create({
  page: {
    flexDirection: 'column',
    backgroundColor: '#ffffff',
    padding: 40,
    fontFamily: 'Helvetica',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 24,
    paddingBottom: 12,
    borderBottom: '1px solid #e5e7eb',
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#111827',
  },
  headerMeta: {
    fontSize: 9,
    color: '#6b7280',
  },
  section: {
    marginBottom: 20,
  },
  sectionTitle: {
    fontSize: 12,
    fontWeight: 'bold',
    color: '#374151',
    marginBottom: 8,
    paddingBottom: 4,
    borderBottom: '1px solid #f3f4f6',
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 4,
  },
  label: {
    fontSize: 9,
    color: '#6b7280',
    width: '40%',
  },
  value: {
    fontSize: 9,
    color: '#111827',
    width: '60%',
    textAlign: 'right',
  },
  kpiGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 8,
  },
  kpiCard: {
    width: '22%',
    padding: 8,
    backgroundColor: '#f9fafb',
    borderRadius: 4,
    border: '1px solid #e5e7eb',
  },
  kpiLabel: {
    fontSize: 8,
    color: '#6b7280',
    marginBottom: 2,
  },
  kpiValue: {
    fontSize: 14,
    fontWeight: 'bold',
    color: '#111827',
  },
  kpiChange: {
    fontSize: 8,
    marginTop: 2,
  },
  table: {
    marginTop: 4,
  },
  tableHeader: {
    flexDirection: 'row',
    backgroundColor: '#f3f4f6',
    padding: '4 6',
    marginBottom: 2,
  },
  tableRow: {
    flexDirection: 'row',
    padding: '3 6',
    borderBottom: '1px solid #f3f4f6',
  },
  tableCell: {
    fontSize: 8,
    color: '#374151',
  },
  footer: {
    position: 'absolute',
    bottom: 24,
    left: 40,
    right: 40,
    flexDirection: 'row',
    justifyContent: 'space-between',
    borderTop: '1px solid #e5e7eb',
    paddingTop: 6,
  },
  footerText: {
    fontSize: 8,
    color: '#9ca3af',
  },
})
