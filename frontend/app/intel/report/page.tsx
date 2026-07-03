'use client';

import { useState } from 'react';
import { intel } from '@/lib/api';
import { CompanyReport } from '@/components/CompanyReport';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Search } from 'lucide-react';
import { useToast } from '@/components/ui/use-toast';

export default function ReportPage() {
  const [company, setCompany] = useState('');
  const [report, setReport] = useState('');
  const [loading, setLoading] = useState(false);
  const { toast } = useToast();

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!company.trim()) return;

    setLoading(true);
    setReport('');

    try {
      const data = await intel.getCompanyReport(company);
      if (data.report) {
        setReport(data.report);
      } else {
        toast({
          title: "No report generated",
          description: "Could not generate a report for this company.",
          variant: "destructive"
        });
      }
    } catch (error) {
      console.error(error);
      toast({
        title: "Error",
        description: "Failed to generate report. Please try again.",
        variant: "destructive"
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-full overflow-auto container mx-auto px-4 max-w-5xl py-8">
      <h1 className="text-3xl font-bold text-foreground mb-8">Company Intelligence Report</h1>

      <Card className="mb-8">
        <CardHeader>
          <CardTitle>Generate Report</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleGenerate} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="company">Company name</Label>
              <Input
                id="company"
                placeholder="e.g., Intel, Microsoft..."
                value={company}
                onChange={(e) => setCompany(e.target.value)}
              />
            </div>
            <Button type="submit" disabled={loading}>
              {loading ? 'Generating...' : (
                <>
                  <Search className="h-4 w-4 mr-2" />
                  Generate
                </>
              )}
            </Button>
          </form>
        </CardContent>
      </Card>

      {(loading || report) && (
        <CompanyReport markdown={report} loading={loading} />
      )}
    </div>
  );
}
