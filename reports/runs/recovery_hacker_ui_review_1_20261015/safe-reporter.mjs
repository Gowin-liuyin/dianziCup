import fs from 'node:fs';

export default class SafeReporter {
  constructor() { this.tests = []; this.errors = 0; }
  onBegin(config, suite) { this.startedAt = new Date().toISOString(); this.discoveredTests = suite.allTests().length; }
  onTestEnd(test, result) {
    const attachments = result.attachments.filter(item => item.contentType === 'application/json' && item.body).map(item => ({name:item.name, value:JSON.parse(item.body.toString('utf8'))}));
    this.tests.push({ title: test.title, file: test.location.file, line: test.location.line, status: result.status, duration_ms: result.duration, error_count: result.errors.length, attachments });
  }
  onError() { this.errors += 1; }
  onEnd(result) {
    const report = { start: this.startedAt, end: new Date().toISOString(), status: result.status, discovered_tests: this.discoveredTests, passed: this.tests.filter(test => test.status === 'passed').length, failed: this.tests.filter(test => test.status === 'failed' || test.status === 'timedOut').length, skipped: this.tests.filter(test => test.status === 'skipped').length, infrastructure_errors: this.errors, tests:this.tests, safety: { trace:'off', video:'off', automatic_screenshots:'off', error_contents_omitted:true, credentials_not_recorded:true } };
    fs.writeFileSync('D:/dianzi/reports/runs/recovery_hacker_ui_review_1_20261015/real_browser_report.safe.json', JSON.stringify(report, null, 2));
    process.stdout.write(JSON.stringify({status:report.status, passed:report.passed, failed:report.failed, skipped:report.skipped, infrastructure_errors:report.infrastructure_errors}) + '\n');
  }
}
